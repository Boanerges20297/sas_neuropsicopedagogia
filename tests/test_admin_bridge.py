"""Offline checks for encrypted admin transport, without production credentials."""
import base64
from contextlib import closing, redirect_stdout
from io import StringIO
import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from scripts.saas_admin_bridge import export_admin


class AdminBridgeTests(unittest.TestCase):
    def test_export_seals_admin_hash_without_plaintext(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "local.sqlite"
            conn = sqlite3.connect(str(db))
            conn.execute("CREATE TABLE users(nome TEXT,email TEXT,senha_hash TEXT,role TEXT,must_change_password INTEGER)")
            sample_hash = "$2b$12$" + "x" * 53
            conn.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                         ("Admin Teste", "admin@example.invalid", sample_hash, "admin", 1))
            conn.commit()
            conn.close()
            private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
            pub_file = root / "public.pem"
            pub_file.write_bytes(private.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo))
            output = StringIO()
            with redirect_stdout(output):
                export_admin(db, pub_file)
            sealed = output.getvalue().strip()
            self.assertNotIn("admin@example.invalid", sealed)
            self.assertNotIn(sample_hash, sealed)
            packet = json.loads(base64.b64decode(sealed))
            aes_key = private.decrypt(base64.b64decode(packet["key"]), padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(), label=None))
            clear = AESGCM(aes_key).decrypt(
                base64.b64decode(packet["nonce"]), base64.b64decode(packet["data"]),
                b"neuro-saas-admin-v1")
            item = json.loads(clear)
            self.assertEqual(item["email"], "admin@example.invalid")
            self.assertEqual(item["senha_hash"], sample_hash)
            self.assertEqual(item["must_change_password"], 1)

    def test_export_aborts_with_no_admin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "local.sqlite"
            with closing(sqlite3.connect(str(db))) as conn:
                conn.execute("CREATE TABLE users(nome TEXT,email TEXT,senha_hash TEXT,role TEXT,must_change_password INTEGER)")
            with self.assertRaises(SystemExit):
                export_admin(db, root / "nonexistent.pem")


if __name__ == "__main__":
    unittest.main()
