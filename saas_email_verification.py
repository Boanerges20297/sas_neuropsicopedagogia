"""Proof of email ownership for all newly created SaaS login identities.

An existing account without verification metadata is legacy (not falsely
claimed verified). New accounts are denied login until the 6-digit OTP is
confirmed. A bootstrap administrator may be reassigned only if untouched,
without MFA enrollment or clinical activity.
"""
from datetime import datetime, timedelta, timezone
import hmac
import os
import re
import secrets

import pymysql
import saas_store as store
import saas_email_otp_transport as mail

EMAIL_CODE_RE = re.compile(r"[0-9]{6}\Z")
TTL_MINUTES = 10
MAX_ATTEMPTS = 5
MAX_SENDS_HOUR = 3


def _utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _secret():
    value = os.getenv("SECRET_KEY", "")
    if len(value) < 32:
        raise RuntimeError("SECRET_KEY longa exigida para verificar e-mail")
    return value.encode("utf-8")


def _normalize(value):
    email = (value or "").strip().lower()
    if len(email) > 254 or not store.EMAIL_RE.fullmatch(email):
        raise ValueError("E-mail invalido")
    return email


def _digest(user_id, email, purpose, nonce, code):
    payload = (b"saas-email-verification-v1:" +
               str(int(user_id)).encode("ascii") + b":" +
               email.encode("utf-8") + b":" + purpose.encode("ascii") +
               b":" + bytes(nonce) + b":" + code.encode("ascii"))
    return hmac.digest(_secret(), payload, "sha256")


def enrollment_required(cur, user_id):
    """Call inside the transaction that creates ANY login account."""
    cur.execute(
        "INSERT INTO saas_email_verifications(user_id,required,verified_at) "
        "VALUES(%s,1,NULL)", (user_id,))


def needs_verification(user_id):
    row = store.one(
        "SELECT required,verified_at FROM saas_email_verifications "
        "WHERE user_id=%s", (user_id,))
    return bool(row and row["required"] and row["verified_at"] is None)


def _bootstrap_record(cur, user_id):
    # Only boolean activity/existence indicators, never clinical content.
    cur.execute("""
        SELECT u.id,u.global_role,u.active,u.must_change_password,
           EXISTS(SELECT 1 FROM audit_events a
             WHERE a.actor_id=u.id AND a.action='admin_saas_bootstrap') AS bootstrapped,
           EXISTS(SELECT 1 FROM audit_events a
             WHERE a.actor_id=u.id AND a.action<>'admin_saas_bootstrap') AS acted,
           EXISTS(SELECT 1 FROM saas_mfa_factors f
             WHERE f.user_id=u.id AND f.enabled_at IS NOT NULL) AS mfa_enabled,
           EXISTS(SELECT 1 FROM clients c JOIN tenants t ON t.id=c.tenant_id
             WHERE t.owner_user_id=u.id) AS has_clients,
           EXISTS(SELECT 1 FROM assessments a JOIN tenants t ON t.id=a.tenant_id
             WHERE t.owner_user_id=u.id) AS has_assessments,
           EXISTS(SELECT 1 FROM care_encounters e JOIN tenants t ON t.id=e.tenant_id
             WHERE t.owner_user_id=u.id) AS has_encounters,
           EXISTS(SELECT 1 FROM care_patient_intakes i
             WHERE i.professional_user_id=u.id) AS has_intakes
        FROM users u WHERE u.id=%s FOR UPDATE
    """, (user_id,))
    return cur.fetchone()


def _bootstrap_allowed(row):
    return bool(row and row["global_role"] == "admin" and row["active"]
                and row["bootstrapped"] and not row["acted"]
                and not row["mfa_enabled"] and not row["has_clients"]
                and not row["has_assessments"] and not row["has_encounters"]
                and not row["has_intakes"])


def bootstrap_eligible(user_id):
    with store.transaction() as cur:
        return _bootstrap_allowed(_bootstrap_record(cur, user_id))


def _prepare(user_id, email, purpose, actor_id=None):
    if not mail.is_ready():
        return None
    dest = _normalize(email)
    now = _utc()
    code = f"{secrets.randbelow(1000000):06d}"
    nonce = secrets.token_bytes(16)
    with store.transaction() as cur:
        cur.execute("SELECT id,email,global_role,active FROM users "
                    "WHERE id=%s FOR UPDATE", (user_id,))
        user = cur.fetchone()
        if not user:
            return None
        cur.execute("SELECT required,verified_at,last_sent_at,send_window_at,"
                    "sends_in_window FROM saas_email_verifications "
                    "WHERE user_id=%s FOR UPDATE", (user_id,))
        verification = cur.fetchone()
        if purpose == "registration":
            if (not verification or not verification["required"]
                    or verification["verified_at"] is not None
                    or user["email"] != dest):
                return None
        elif purpose == "confirm_current":
            if actor_id != user_id or not user["active"] or dest != user["email"]:
                raise PermissionError("Confirmacao de endereco nao autorizada")
            if verification and (verification["verified_at"] is not None
                                 or verification["required"]):
                return None
            if verification is None:
                cur.execute(
                    "INSERT INTO saas_email_verifications(user_id,required,verified_at) "
                    "VALUES(%s,0,NULL)", (user_id,))
        elif purpose == "change":
            if actor_id != user_id or not user["active"] or dest == user["email"]:
                raise PermissionError("Troca de e-mail nao permitida")
            if verification is None:
                cur.execute(
                    "INSERT INTO saas_email_verifications(user_id,required,verified_at) "
                    "VALUES(%s,0,NULL)", (user_id,))
        elif purpose == "bootstrap_admin":
            cur.execute("SELECT id,global_role,active FROM users WHERE id=%s",
                        (actor_id,))
            actor = cur.fetchone()
            if (not actor or not actor["active"] or
                    actor["global_role"] != "superadmin" or actor_id == user_id):
                raise PermissionError("Somente SuperAdmin pode regularizar o bootstrap")
            if not _bootstrap_allowed(_bootstrap_record(cur, user_id)):
                raise PermissionError("Conta inicial com atividade ou autenticador nao elegivel")
            if verification and verification["verified_at"] is not None:
                raise PermissionError("E-mail anteriormente verificado exige titular")
            if verification is None:
                cur.execute(
                    "INSERT INTO saas_email_verifications(user_id,required,verified_at) "
                    "VALUES(%s,1,NULL)", (user_id,))
            else:
                cur.execute(
                    "UPDATE saas_email_verifications SET required=1,"
                    "verified_at=NULL WHERE user_id=%s", (user_id,))
        else:
            raise ValueError("Finalidade de verificacao invalida")
        if purpose in ("change","bootstrap_admin"):
            cur.execute("SELECT id FROM users WHERE email=%s FOR UPDATE", (dest,))
            if cur.fetchone():
                raise ValueError("E-mail ja cadastrado")
        previous = verification or {}
        last = previous.get("last_sent_at")
        window = previous.get("send_window_at")
        sends = int(previous.get("sends_in_window") or 0)
        if last and last + timedelta(seconds=60) > now:
            return None
        if not window or window + timedelta(hours=1) <= now:
            window, sends = now, 0
        if sends >= MAX_SENDS_HOUR:
            return None
        # Release expired addresses; active challenges remain exclusive.
        cur.execute("DELETE FROM saas_email_challenges WHERE expires_at<=%s",
                    (now,))
        cur.execute("SELECT user_id FROM saas_email_challenges "
                    "WHERE requested_email=%s FOR UPDATE",(dest,))
        address_owner=cur.fetchone()
        if address_owner and int(address_owner["user_id"])!=user_id:
            raise ValueError("Confirmacao pendente para este endereco")
        cur.execute("SELECT user_id FROM saas_email_challenges "
                    "WHERE user_id=%s FOR UPDATE",(user_id,))
        previous_challenge=cur.fetchone()
        parameters=(dest,purpose,nonce,
                    _digest(user_id,dest,purpose,nonce,code),
                    now+timedelta(minutes=TTL_MINUTES),MAX_ATTEMPTS,actor_id)
        if previous_challenge:
            cur.execute("""
                UPDATE saas_email_challenges
                SET requested_email=%s,purpose=%s,nonce=%s,digest=%s,
                    expires_at=%s,attempts_left=%s,requested_by=%s
                WHERE user_id=%s
            """,parameters+(user_id,))
        else:
            cur.execute("""
                INSERT INTO saas_email_challenges
                    (requested_email,purpose,nonce,digest,expires_at,
                     attempts_left,requested_by,user_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,parameters+(user_id,))
        cur.execute("""
            UPDATE saas_email_verifications
            SET last_sent_at=%s,send_window_at=%s,sends_in_window=%s
            WHERE user_id=%s
        """, (now,window,sends+1,user_id))
        store.audit(cur, actor_id or user_id, None,
                    "email_verification_sent", "user", user_id,
                    reason="purpose="+purpose)
    try:
        mail.send_verification_code(dest,code)
    except mail.EmailOtpUnavailable:
        with store.transaction() as cur:
            cur.execute(
                "UPDATE saas_email_challenges SET expires_at=UTC_TIMESTAMP(),"
                "attempts_left=0 WHERE user_id=%s AND nonce=%s",
                (user_id,nonce))
        return None
    return True


def request_registration_code(email):
    dest = _normalize(email)
    row = store.one("SELECT id FROM users WHERE email=%s",(dest,))
    return bool(row and _prepare(int(row["id"]),dest,"registration"))


def request_change_code(user_id, email):
    return bool(_prepare(int(user_id),email,"change",actor_id=int(user_id)))


def request_current_code(user_id, email):
    return bool(_prepare(int(user_id),email,"confirm_current",actor_id=int(user_id)))


def request_bootstrap_code(actor_id, target_id, new_email):
    return bool(_prepare(int(target_id),new_email,
                         "bootstrap_admin",actor_id=int(actor_id)))


def confirm_code(email, code, *, authenticated_user_id=None):
    if not isinstance(code,str) or not EMAIL_CODE_RE.fullmatch(code):
        return False
    dest = _normalize(email)
    now = _utc()
    with store.transaction() as cur:
        cur.execute("""
            SELECT c.user_id,c.purpose,c.nonce,c.digest,c.expires_at,
                   c.attempts_left,c.requested_by,u.email AS old_email,
                   u.global_role,u.active
            FROM saas_email_challenges c
            JOIN users u ON u.id=c.user_id
            WHERE c.requested_email=%s FOR UPDATE
        """, (dest,))
        item=cur.fetchone()
        if (not item or item["expires_at"]<=now
                or int(item["attempts_left"])<=0):
            return False
        uid=int(item["user_id"])
        purpose=item["purpose"]
        if purpose in ("change","confirm_current") and authenticated_user_id!=uid:
            return False
        if purpose in ("registration","confirm_current") and item["old_email"]!=dest:
            return False
        if purpose=="bootstrap_admin":
            if not item["requested_by"] or int(item["requested_by"])==uid:
                return False
            cur.execute("SELECT active,global_role FROM users WHERE id=%s",
                        (item["requested_by"],))
            operator=cur.fetchone()
            if (not operator or not operator["active"]
                    or operator["global_role"]!="superadmin"):
                return False
            if not _bootstrap_allowed(_bootstrap_record(cur,uid)):
                return False
        if not hmac.compare_digest(bytes(item["digest"]),
                _digest(uid,dest,purpose,item["nonce"],code)):
            cur.execute("UPDATE saas_email_challenges "
                        "SET attempts_left=attempts_left-1 WHERE user_id=%s",
                        (uid,))
            return False
        if purpose in ("change","bootstrap_admin"):
            if purpose=="bootstrap_admin":
                # Old credentials MUST stop working after this identity repair.
                # The titular sets a new password through verified-email OTP.
                from app import bcrypt
                disabled_hash=bcrypt.generate_password_hash(
                    secrets.token_urlsafe(48)).decode()
                cur.execute(
                    "UPDATE users SET email=%s,password_hash=%s,"
                    "must_change_password=1 WHERE id=%s",
                    (dest,disabled_hash,uid))
            else:
                cur.execute("UPDATE users SET email=%s WHERE id=%s",(dest,uid))
            cur.execute(
                "UPDATE saas_mfa_trusted_devices SET revoked_at=UTC_TIMESTAMP() "
                "WHERE user_id=%s AND revoked_at IS NULL", (uid,))
            cur.execute(
                "UPDATE saas_password_recovery_otp SET "
                "expires_at=UTC_TIMESTAMP(),attempts_left=0 "
                "WHERE user_id=%s", (uid,))
        cur.execute(
            "UPDATE saas_email_verifications SET required=1,"
            "verified_at=UTC_TIMESTAMP() WHERE user_id=%s", (uid,))
        cur.execute("DELETE FROM saas_email_challenges WHERE user_id=%s",(uid,))
        store.audit(cur,item["requested_by"] or uid,None,
                    "email_verified_"+purpose,"user",uid)
    return purpose


def pending_status(email):
    dest=_normalize(email)
    return bool(store.one(
        """SELECT 1 FROM users u JOIN saas_email_verifications v
             ON v.user_id=u.id
             WHERE u.email=%s AND v.required=1 AND v.verified_at IS NULL""",
        (dest,)))
