"""One-time encrypted transfer of a TEST admin from local SQLite to SaaS MySQL.

Export on the developer notebook with the VPS's ephemeral RSA PUBLIC key.
Import only inside the Flask container using its matching PRIVATE key.
Never print email, password hashes, plaintext or transport private keys.
This script is passed to container stdin; it is NOT baked into the web image.
"""
import base64
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64(data):
    return base64.b64encode(data).decode("ascii")


def unb64(data):
    return base64.b64decode(data, validate=True)


def export_admin(db_path, public_key_path):
    source = Path(db_path).resolve()
    with closing(sqlite3.connect("file:" + source.as_posix() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT nome,email,senha_hash,role,must_change_password "
            "FROM users WHERE role IN ('admin','superadmin')"
        ).fetchall()
    if len(rows) != 1:
        raise SystemExit("EXPORT_ABORTED: exactly one local test administrator required")
    admin = dict(rows[0])
    if not str(admin["senha_hash"]).startswith(("$2a$", "$2b$", "$2y$")):
        raise SystemExit("EXPORT_ABORTED: unsupported bcrypt hash format")
    pub = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
    if not isinstance(pub, rsa.RSAPublicKey) or pub.key_size < 3072:
        raise SystemExit("EXPORT_ABORTED: RSA public key must be 3072 bits or larger")
    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    cleartext = json.dumps(admin, ensure_ascii=False, separators=(",", ":")).encode()
    encrypted = AESGCM(aes_key).encrypt(nonce, cleartext, b"neuro-saas-admin-v1")
    wrapped_key = pub.encrypt(aes_key, padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    packet = {"v": 1, "key": b64(wrapped_key), "nonce": b64(nonce), "data": b64(encrypted)}
    print(b64(json.dumps(packet, separators=(",", ":")).encode()))


def import_admin(private_key_path):
    sealed = os.environ.get("SAAS_ADMIN_SEALED", "")
    if not sealed or len(sealed) > 16000:
        raise SystemExit("IMPORT_ABORTED: sealed payload missing or oversized")
    packet = json.loads(unb64(sealed))
    if packet.get("v") != 1:
        raise SystemExit("IMPORT_ABORTED: unsupported sealed payload")
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    aes_key = key.decrypt(unb64(packet["key"]), padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    admin = json.loads(AESGCM(aes_key).decrypt(
        unb64(packet["nonce"]), unb64(packet["data"]), b"neuro-saas-admin-v1"))
    if (admin.get("role") not in ("admin", "superadmin")
            or not str(admin.get("senha_hash", "")).startswith(("$2a$", "$2b$", "$2y$"))
            or not str(admin.get("email", "")).strip()
            or not str(admin.get("nome", "")).strip()):
        raise SystemExit("IMPORT_ABORTED: invalid administrator record")
    from saas_store import transaction
    with transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM users WHERE global_role IN ('admin','superadmin')")
        if cur.fetchone()["n"]:
            raise SystemExit("IMPORT_ABORTED: SaaS administrator already exists")
        cur.execute("SELECT 1 FROM users WHERE email=%s", (admin["email"],))
        if cur.fetchone():
            raise SystemExit("IMPORT_ABORTED: email already exists under another role")
        cur.execute(
            "INSERT INTO users (nome,email,password_hash,global_role,active,must_change_password) "
            "VALUES (%s,%s,%s,%s,1,%s)",
            (admin["nome"], admin["email"].strip().lower(), admin["senha_hash"],
             admin["role"], int(bool(admin.get("must_change_password", False)))))
        uid = cur.lastrowid
        slug = "admin-" + uuid4().hex
        cur.execute("INSERT INTO tenants (nome,slug,owner_user_id,status) "
                    "VALUES (%s,%s,%s,'active')", (admin["nome"], slug, uid))
        tid = cur.lastrowid
        cur.execute("INSERT INTO tenant_members (tenant_id,user_id,membership_role,status) "
                    "VALUES (%s,%s,'owner','active')", (tid, uid))
        cur.execute(
            "INSERT INTO professional_profiles (user_id,profession,verification_status,verified_at) "
            "VALUES (%s,'neuropsicopedagogo','verified',NOW())", (uid,))
        cur.execute(
            "INSERT INTO audit_events (actor_id,tenant_id,action,resource_type,resource_id,access_reason,outcome) "
            "VALUES (%s,%s,'admin_saas_bootstrap','tenant',%s,'encrypted test account transfer','allowed')",
            (uid, tid, tid))
    print("SAAS_TEST_ADMIN_READY | tenant active | existing password hash preserved")


if __name__ == "__main__":
    if len(sys.argv) != 4 and not (len(sys.argv) == 3 and sys.argv[1] == "import"):
        raise SystemExit("usage: export <sqlite_file> <rsa_public.pem> | import <rsa_private.pem>")
    if sys.argv[1] == "export":
        export_admin(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "import":
        import_admin(sys.argv[2])
    else:
        raise SystemExit("Invalid mode")
