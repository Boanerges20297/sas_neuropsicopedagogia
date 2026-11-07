"""Persistent account login throttling and four-digit email recovery OTP.

Mail delivery stays disabled until the owner configures the dedicated SMTP.
Five password failures trigger a 10-minute cooldown (not permanent lockout).
Email OTP: 3-minute TTL, 3 verification attempts, one use, max 3 sends/hour,
at least 60 seconds between sends. No account existence leaks in route replies.
"""
from datetime import datetime, timedelta, timezone
import hmac
import os
import secrets

import saas_email_otp_transport as mail
import saas_store as store

MAX_FAILURES = 5
WINDOW_MINUTES = 15
COOLDOWN_MINUTES = 10
OTP_MINUTES = 3
OTP_ATTEMPTS = 3


def _utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _secret():
    key = os.getenv("SECRET_KEY", "")
    if len(key) < 32:
        raise RuntimeError("SECRET_KEY longa exigida para OTP")
    return key.encode("utf-8")


def _key(email):
    return hmac.digest(_secret(),
                       b"login-limit-v1:" + (email or "").strip().lower().encode(),
                       "sha256")


def _digest(uid, nonce, code):
    return hmac.digest(
        _secret(), b"email-recovery-v1:" + str(int(uid)).encode("ascii")
        + b":" + bytes(nonce) + b":" + code.encode("ascii"), "sha256")


def random_code():
    return f"{secrets.randbelow(10000):04d}"


def cooldown_remaining(email):
    row = store.one(
        "SELECT cooldown_until FROM saas_login_attempt_limits WHERE principal_digest=%s",
        (_key(email),))
    if row and row["cooldown_until"] and row["cooldown_until"] > _utc():
        return max(1, int((row["cooldown_until"] - _utc()).total_seconds()))
    return 0


def note_wrong_password(email):
    now = _utc()
    key = _key(email)
    with store.transaction() as cur:
        cur.execute(
            """SELECT failures,started_at,cooldown_until
               FROM saas_login_attempt_limits WHERE principal_digest=%s FOR UPDATE""",
            (key,))
        row = cur.fetchone()
        if row and row["cooldown_until"] and row["cooldown_until"] > now:
            return True
        failures, started = 1, now
        if (row and row["started_at"]
                and row["started_at"] + timedelta(minutes=WINDOW_MINUTES) > now):
            failures, started = int(row["failures"]) + 1, row["started_at"]
        cooldown = now + timedelta(minutes=COOLDOWN_MINUTES) if failures >= MAX_FAILURES else None
        cur.execute(
            """INSERT INTO saas_login_attempt_limits
                 (principal_digest,failures,started_at,cooldown_until)
               VALUES(%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 failures=VALUES(failures),started_at=VALUES(started_at),
                 cooldown_until=VALUES(cooldown_until)""",
            (key, min(MAX_FAILURES,failures), started, cooldown))
        return bool(cooldown)


def clear_failures(email):
    with store.transaction() as cur:
        cur.execute("DELETE FROM saas_login_attempt_limits WHERE principal_digest=%s",
                    (_key(email),))


def request_reset(email):
    """Do not automatically send after failed logins; user explicitly requests it."""
    normalized = (email or "").strip().lower()
    if not mail.is_ready() or len(normalized)>254 or not store.EMAIL_RE.fullmatch(normalized):
        return False
    code = random_code()
    nonce = secrets.token_bytes(16)
    now = _utc()
    with store.transaction() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s AND active=1", (normalized,))
        row = cur.fetchone()
        if not row:
            return False
        uid = int(row["id"])
        cur.execute(
            """SELECT last_sent_at,send_window_at,sends_in_window
               FROM saas_password_recovery_otp WHERE user_id=%s FOR UPDATE""",
            (uid,))
        previous = cur.fetchone()
        sends, window = 0, now
        if previous:
            if previous["last_sent_at"] + timedelta(seconds=60) > now:
                return False
            if previous["send_window_at"] + timedelta(hours=1) > now:
                sends, window = int(previous["sends_in_window"]), previous["send_window_at"]
        if sends >= 3:
            return False
        cur.execute(
            """INSERT INTO saas_password_recovery_otp
                 (user_id,nonce,digest,expires_at,attempts_left,
                  last_sent_at,send_window_at,sends_in_window,used_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NULL)
               ON DUPLICATE KEY UPDATE nonce=VALUES(nonce),digest=VALUES(digest),
                 expires_at=VALUES(expires_at),attempts_left=VALUES(attempts_left),
                 last_sent_at=VALUES(last_sent_at),send_window_at=VALUES(send_window_at),
                 sends_in_window=VALUES(sends_in_window),used_at=NULL""",
            (uid,nonce,_digest(uid,nonce,code),now+timedelta(minutes=OTP_MINUTES),
             OTP_ATTEMPTS,now,window,sends+1))
    try:
        mail.send_code(normalized, code)
    except mail.EmailOtpUnavailable:
        with store.transaction() as cur:
            cur.execute(
                """UPDATE saas_password_recovery_otp
                   SET expires_at=UTC_TIMESTAMP(),attempts_left=0
                   WHERE user_id=%s AND nonce=%s AND used_at IS NULL""",
                (uid,nonce))
        return False
    return True


def reset_with_code(email, code, new_hash):
    normalized = (email or "").strip().lower()
    if (not mail.is_ready() or not isinstance(code,str) or len(code)!=4
            or not code.isascii() or not code.isdigit()
            or not isinstance(new_hash,str) or not 20<=len(new_hash)<=255):
        return False
    now = _utc()
    with store.transaction() as cur:
        cur.execute(
            """SELECT u.id,u.active,r.nonce,r.digest,r.expires_at,
                      r.attempts_left,r.used_at
               FROM users u JOIN saas_password_recovery_otp r ON r.user_id=u.id
               WHERE u.email=%s FOR UPDATE""", (normalized,))
        row = cur.fetchone()
        if (not row or not row["active"] or row["used_at"]
                or row["expires_at"]<=now or int(row["attempts_left"])<=0):
            return False
        if not hmac.compare_digest(bytes(row["digest"]),_digest(row["id"],row["nonce"],code)):
            cur.execute(
                """UPDATE saas_password_recovery_otp
                   SET attempts_left=attempts_left-1 WHERE user_id=%s""",
                (row["id"],))
            return False
        cur.execute(
            "UPDATE users SET password_hash=%s,must_change_password=0 WHERE id=%s AND active=1",
            (new_hash,row["id"]))
        cur.execute(
            """UPDATE saas_password_recovery_otp
               SET used_at=UTC_TIMESTAMP(),attempts_left=0 WHERE user_id=%s""",
            (row["id"],))
        cur.execute(
            """UPDATE saas_mfa_trusted_devices SET revoked_at=UTC_TIMESTAMP()
               WHERE user_id=%s AND revoked_at IS NULL""", (row["id"],))
        cur.execute("DELETE FROM saas_login_attempt_limits WHERE principal_digest=%s",
                    (_key(normalized),))
        store.audit(cur,row["id"],None,"password_recovery_email_otp","user",row["id"])
        return True
