"""Superadmin SMTP setup: one Gmail identity, encrypted password at rest.

The setup secret is accepted only through a CSRF-protected HTTPS POST.
Activation requires a code sent to the dedicated sender mailbox.
"""
import base64
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import saas_store as store

SENDER = "neuro-diagnosis47@gmail.com"
HOST = "smtp.gmail.com"
PORT = 465


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _secret():
    key = os.getenv("SECRET_KEY", "")
    if len(key) < 32:
        raise RuntimeError("Configuração de chave secreta inválida")
    return key.encode("utf-8")


def _cipher():
    material = HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=b"neuro-diagnosis-smtp-2026",
        info=b"saas-smtp-key-v1",
    ).derive(_secret())
    return Fernet(base64.urlsafe_b64encode(material))


def _normalise_app_password(password):
    if not isinstance(password, str):
        raise ValueError("Senha de app inválida")
    value = "".join(password.split())
    if not re.fullmatch(r"[A-Za-z]{16}", value):
        raise ValueError("Use a senha de app Google de 16 letras")
    return value


def _public(row):
    return {
        "configured": bool(row),
        "enabled": bool(row and row["enabled"]),
        "verified": bool(row and row["verified_at"]),
        "sender": SENDER,
    }


def status():
    row = store.one(
        "SELECT enabled,verified_at FROM saas_smtp_settings WHERE id=1")
    return _public(row)


def save_password(actor_id, new_password):
    value = _normalise_app_password(new_password)
    encrypted = _cipher().encrypt(value.encode("ascii"))
    with store.transaction() as cur:
        cur.execute(
            """INSERT INTO saas_smtp_settings
               (id,sender,password_cipher,enabled,updated_by)
               VALUES(1,%s,%s,0,%s)
               ON DUPLICATE KEY UPDATE sender=VALUES(sender),
                  password_cipher=VALUES(password_cipher),enabled=0,
                  test_nonce=NULL,test_digest=NULL,test_expires_at=NULL,
                  test_attempts=0,test_sent_at=NULL,verified_at=NULL,
                  updated_by=VALUES(updated_by)""",
            (SENDER, encrypted, actor_id))
        store.audit(cur, actor_id, None, "smtp_credentials_configured",
                    "user", actor_id, reason="email_recovery_setup")


def _read_secret(row):
    if not row or row["sender"] != SENDER:
        return None
    value = _cipher().decrypt(bytes(row["password_cipher"])).decode("ascii")
    return {
        "host":HOST,"port":PORT,"security":"ssl",
        "user":SENDER,"from":SENDER,"password":value,
    }


def active_transport():
    row = store.one(
        """SELECT sender,password_cipher FROM saas_smtp_settings
           WHERE id=1 AND enabled=1 AND verified_at IS NOT NULL""")
    return _read_secret(row)


def draft_transport():
    row = store.one(
        "SELECT sender,password_cipher FROM saas_smtp_settings WHERE id=1")
    return _read_secret(row)


def begin_verification():
    """One e-mail per 60 seconds; no arbitrary recipients."""
    code = f"{secrets.randbelow(1000000):06d}"
    nonce = secrets.token_bytes(16)
    now = _now()
    digest = hmac.digest(_secret(), nonce + code.encode(), "sha256")
    with store.transaction() as cur:
        cur.execute(
            """SELECT test_sent_at FROM saas_smtp_settings
               WHERE id=1 FOR UPDATE""")
        row = cur.fetchone()
        if not row:
            raise ValueError("Configure a senha de app antes de testar")
        if row["test_sent_at"] and row["test_sent_at"] + timedelta(seconds=60) > now:
            raise ValueError("Aguarde 60 segundos antes de solicitar outro teste")
        cur.execute(
            """UPDATE saas_smtp_settings
               SET enabled=0,test_nonce=%s,test_digest=%s,
                   test_expires_at=%s,test_attempts=0,test_sent_at=%s
               WHERE id=1""",
            (nonce,digest,now+timedelta(minutes=10),now))
    return code


def invalidate_verification():
    with store.transaction() as cur:
        cur.execute(
            """UPDATE saas_smtp_settings SET test_nonce=NULL,
               test_digest=NULL,test_expires_at=NULL,enabled=0 WHERE id=1""")


def confirm_verification(actor_id, code):
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{6}",code):
        return False
    now = _now()
    with store.transaction() as cur:
        cur.execute(
            """SELECT test_nonce,test_digest,test_expires_at,test_attempts
               FROM saas_smtp_settings WHERE id=1 FOR UPDATE""")
        row = cur.fetchone()
        if (not row or not row["test_nonce"] or not row["test_digest"]
                or not row["test_expires_at"] or row["test_expires_at"] <= now
                or int(row["test_attempts"]) >= 3):
            return False
        digest = hmac.digest(_secret(),bytes(row["test_nonce"]) + code.encode(),"sha256")
        if not hmac.compare_digest(bytes(row["test_digest"]),digest):
            cur.execute(
                "UPDATE saas_smtp_settings SET test_attempts=test_attempts+1 WHERE id=1")
            return False
        cur.execute(
            """UPDATE saas_smtp_settings
               SET enabled=1,verified_at=UTC_TIMESTAMP(),updated_by=%s,
                   test_nonce=NULL,test_digest=NULL,test_expires_at=NULL
               WHERE id=1""", (actor_id,))
        store.audit(cur, actor_id, None, "smtp_recovery_activated",
                    "user", actor_id, reason="sender_receipt_confirmed")
        return True


def disable(actor_id):
    with store.transaction() as cur:
        cur.execute(
            """UPDATE saas_smtp_settings SET enabled=0,updated_by=%s,
               test_nonce=NULL,test_digest=NULL,test_expires_at=NULL
               WHERE id=1""",(actor_id,))
        store.audit(cur, actor_id, None, "smtp_recovery_disabled",
                    "user", actor_id)
