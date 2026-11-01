"""Provision local S2S identity once. Never output or commit private key."""
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from dotenv import set_key
import os
ROOT=Path(__file__).resolve().parents[1]
SECRET_DIR=ROOT/".secrets"
KEY=SECRET_DIR/"bta-neuro-prod-v1-private.pem"
PUBLIC=ROOT/"scripts"/"bta-neuro-prod-v1-public.pem"
SECRET_DIR.mkdir(exist_ok=True)
if not KEY.exists():
    private=Ed25519PrivateKey.generate()
    data=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY
    descriptor=os.open(str(KEY),flags,0o600)
    with os.fdopen(descriptor,"wb") as f:f.write(data)
else:
    private=serialization.load_pem_private_key(KEY.read_bytes(),password=None)
    if not isinstance(private,Ed25519PrivateKey):
        raise RuntimeError("Local key is not Ed25519")
public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
PUBLIC.write_bytes(public)
set_key(str(ROOT/".env"),"BTA_CLIENT_ID","neuro-diagnosis-backend",quote_mode="always")
set_key(str(ROOT/".env"),"BTA_KEY_ID","neuro-diagnosis-prod-v1",quote_mode="always")
set_key(str(ROOT/".env"),"BTA_PRIVATE_KEY_PATH",str(KEY),quote_mode="always")
set_key(str(ROOT/".env"),"BTA_TRIAL_PACKAGE_CODE","experimentar-14-dias",quote_mode="always")
print("S2S_LOCAL_KEY_READY",PUBLIC.name)
