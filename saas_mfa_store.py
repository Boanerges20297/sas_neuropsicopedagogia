"""Transactional MFA enrollment, verification, recovery, and trusted devices."""
from datetime import datetime, timedelta, timezone
import secrets

import saas_store as store
import saas_mfa as crypto

DEVICE_DAYS = 30
ENROLLMENT_MINUTES = 15
LOCK_MINUTES = 10
MAX_ATTEMPTS = 5


def _utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enabled(user_id):
    row = store.one(
        "SELECT enabled_at FROM saas_mfa_factors WHERE user_id=%s", (user_id,))
    return bool(row and row["enabled_at"])


def enrollment_required(user_id):
    """New accounts cannot pass first login until setup is confirmed."""
    row = store.one(
        "SELECT required,enabled_at FROM saas_mfa_factors WHERE user_id=%s",
        (user_id,))
    return bool(row and row["required"] and not row["enabled_at"])


def begin_enrollment(user_id):
    if type(user_id) is not int or user_id <= 0:
        raise PermissionError("Conta inválida")
    seed = crypto.new_seed()
    now = _utc()
    with store.transaction() as cur:
        cur.execute("SELECT id,active FROM users WHERE id=%s FOR UPDATE", (user_id,))
        user = cur.fetchone()
        if not user or not user["active"]:
            raise PermissionError("Conta não autorizada")
        cur.execute(
            "SELECT enabled_at FROM saas_mfa_factors WHERE user_id=%s FOR UPDATE",
            (user_id,))
        prior = cur.fetchone()
        if prior and prior["enabled_at"]:
            raise ValueError("TOTP já configurado; a substituição exige recuperação segura")
        cur.execute(
            """INSERT INTO saas_mfa_factors(user_id,pending_cipher,pending_at)
               VALUES(%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 pending_cipher=VALUES(pending_cipher),
                 pending_at=VALUES(pending_at)""",
            (user_id, crypto.seal_seed(user_id, seed), now))
    return seed


def pending_seed(user_id):
    row = store.one(
        """SELECT pending_cipher,pending_at,enabled_at
           FROM saas_mfa_factors WHERE user_id=%s""", (user_id,))
    if not row or row["enabled_at"] or not row["pending_cipher"] or not row["pending_at"]:
        return None
    if row["pending_at"] + timedelta(minutes=ENROLLMENT_MINUTES) < _utc():
        return None
    return crypto.open_seed(user_id, row["pending_cipher"])


def finish_enrollment(user_id, code):
    with store.transaction() as cur:
        cur.execute(
            """SELECT pending_cipher,pending_at,enabled_at
               FROM saas_mfa_factors WHERE user_id=%s FOR UPDATE""", (user_id,))
        row = cur.fetchone()
        if (not row or row["enabled_at"] or not row["pending_cipher"]
                or not row["pending_at"]
                or row["pending_at"] + timedelta(minutes=ENROLLMENT_MINUTES) < _utc()):
            raise ValueError("Configuração expirada. Inicie novamente.")
        seed = crypto.open_seed(user_id, row["pending_cipher"])
        step = crypto.matching_step(seed, code)
        if step is None:
            raise ValueError("Código incorreto ou expirado")
        codes = crypto.recovery_codes()
        cur.execute(
            """UPDATE saas_mfa_factors
               SET secret_cipher=%s,enabled_at=UTC_TIMESTAMP(),
                   pending_cipher=NULL,pending_at=NULL,last_used_step=%s,
                   failed_attempts=0,locked_until=NULL
               WHERE user_id=%s""",
            (row["pending_cipher"], step, user_id))
        cur.execute("DELETE FROM saas_mfa_recovery_codes WHERE user_id=%s", (user_id,))
        cur.executemany(
            """INSERT INTO saas_mfa_recovery_codes(user_id,code_digest)
               VALUES(%s,%s)""",
            [(user_id, crypto.recovery_digest(code)) for code in codes])
        store.audit(cur, user_id, None, "mfa_totp_enabled", "user", user_id)
        return codes


def verify_login_factor(user_id, code):
    """Consume a single-use TOTP or recovery code; return (ok,is_totp)."""
    now = _utc()
    with store.transaction() as cur:
        cur.execute(
            """SELECT secret_cipher,enabled_at,last_used_step,
                      failed_attempts,locked_until
               FROM saas_mfa_factors WHERE user_id=%s FOR UPDATE""",
            (user_id,))
        row = cur.fetchone()
        if not row or not row["enabled_at"] or not row["secret_cipher"]:
            return (False, False)
        if row["locked_until"] and row["locked_until"] > now:
            return (False, False)
        seed = crypto.open_seed(user_id, row["secret_cipher"])
        step = crypto.matching_step(
            seed, code, last_used=int(row["last_used_step"]))
        if step is not None:
            cur.execute(
                """UPDATE saas_mfa_factors SET last_used_step=%s,
                   failed_attempts=0,locked_until=NULL WHERE user_id=%s""",
                (step, user_id))
            store.audit(cur, user_id, None, "mfa_totp_login", "user", user_id)
            return (True, True)
        digest = crypto.recovery_digest(code)
        if digest:
            cur.execute(
                """UPDATE saas_mfa_recovery_codes
                   SET used_at=UTC_TIMESTAMP()
                   WHERE user_id=%s AND code_digest=%s AND used_at IS NULL""",
                (user_id, digest))
            if cur.rowcount == 1:
                cur.execute(
                    """UPDATE saas_mfa_factors SET failed_attempts=0,
                       locked_until=NULL WHERE user_id=%s""", (user_id,))
                store.audit(cur, user_id, None, "mfa_recovery_login", "user", user_id)
                return (True, False)
        fails = int(row["failed_attempts"] or 0) + 1
        locked_until = now + timedelta(minutes=LOCK_MINUTES) if fails >= MAX_ATTEMPTS else None
        cur.execute(
            """UPDATE saas_mfa_factors SET failed_attempts=%s,locked_until=%s
               WHERE user_id=%s""", (fails if not locked_until else 0, locked_until, user_id))
        return (False, False)


def trust_device(user_id, agent):
    token = secrets.token_urlsafe(32)
    digest = crypto.token_digest(token)
    with store.transaction() as cur:
        cur.execute(
            """SELECT enabled_at FROM saas_mfa_factors
               WHERE user_id=%s FOR UPDATE""", (user_id,))
        row = cur.fetchone()
        if not row or not row["enabled_at"]:
            raise PermissionError("Configure TOTP antes de confiar no dispositivo")
        cur.execute(
            """UPDATE saas_mfa_trusted_devices SET revoked_at=UTC_TIMESTAMP()
               WHERE user_id=%s AND revoked_at IS NULL AND expires_at<=UTC_TIMESTAMP()""",
            (user_id,))
        cur.execute(
            """INSERT INTO saas_mfa_trusted_devices
               (user_id,token_digest,user_agent_digest,expires_at)
               VALUES(%s,%s,%s,DATE_ADD(UTC_TIMESTAMP(),INTERVAL 30 DAY))""",
            (user_id, digest, crypto.agent_digest(agent)))
        # Cap active trusted-device count to five; older tokens are revoked.
        cur.execute(
            """UPDATE saas_mfa_trusted_devices
               SET revoked_at=UTC_TIMESTAMP()
               WHERE user_id=%s AND revoked_at IS NULL AND id NOT IN
                 (SELECT id FROM (
                   SELECT id FROM saas_mfa_trusted_devices
                   WHERE user_id=%s AND revoked_at IS NULL
                   ORDER BY id DESC LIMIT 5
                 ) AS recent)""",
            (user_id, user_id))
        store.audit(cur, user_id, None, "mfa_device_trusted", "user", user_id)
    return token


def trusted(user_id, token, agent):
    digest = crypto.token_digest(token)
    if digest is None:
        return False
    with store.transaction() as cur:
        cur.execute(
            """SELECT d.id FROM saas_mfa_trusted_devices d
               JOIN saas_mfa_factors f ON f.user_id=d.user_id
               WHERE d.user_id=%s AND d.token_digest=%s
                 AND d.user_agent_digest=%s
                 AND d.revoked_at IS NULL
                 AND d.expires_at>UTC_TIMESTAMP()
                 AND f.enabled_at IS NOT NULL
               FOR UPDATE""",
            (user_id, digest, crypto.agent_digest(agent)))
        row = cur.fetchone()
        if not row:
            return False
        cur.execute(
            "UPDATE saas_mfa_trusted_devices SET last_seen_at=UTC_TIMESTAMP() WHERE id=%s",
            (row["id"],))
        return True


def revoke_trusted_devices(user_id):
    with store.transaction() as cur:
        cur.execute(
            """UPDATE saas_mfa_trusted_devices SET revoked_at=UTC_TIMESTAMP()
               WHERE user_id=%s AND revoked_at IS NULL""", (user_id,))
        store.audit(cur, user_id, None, "mfa_devices_revoked", "user", user_id)
