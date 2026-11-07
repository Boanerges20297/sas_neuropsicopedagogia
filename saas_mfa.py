"""RFC 6238 TOTP and protection of MFA enrollment secrets.

No SMS, logging of OTP values, or unencrypted MFA seeds.
"""
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import quote, urlencode
import base64
import hmac
import os
import secrets
import struct
import time

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

STEP_SECONDS = 30
OTP_DIGITS = 6
WINDOW_STEPS = 1


def new_seed():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _seed_bytes(seed):
    if not isinstance(seed, str) or len(seed) > 64:
        raise ValueError("Chave TOTP inválida")
    raw = seed.upper().replace(" ", "")
    return base64.b32decode(raw + ("=" * (-len(raw) % 8)), casefold=False)


def totp(seed, counter):
    if type(counter) is not int or counter < 0:
        raise ValueError("Intervalo TOTP inválido")
    digest = hmac.digest(_seed_bytes(seed), struct.pack(">Q", counter), "sha1")
    offset = digest[-1] & 15
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff) % 10**OTP_DIGITS
    return f"{value:06d}"


def matching_step(seed, candidate, *, at=None, last_used=-1):
    if not isinstance(candidate, str) or len(candidate) != 6 or not candidate.isascii() or not candidate.isdigit():
        return None
    at = time.time() if at is None else float(at)
    now_step = int(at // STEP_SECONDS)
    # Honor no-replay even if client clock is skewed.
    for step in (now_step - 1, now_step, now_step + 1):
        if step >= 0 and step > last_used and hmac.compare_digest(totp(seed, step), candidate):
            return step
    return None


def provisioning_uri(seed, email):
    issuer = "Neuro-Diagnosis"
    return "otpauth://totp/" + quote(f"{issuer}:{email}", safe="") + "?" + urlencode({
        "secret": seed, "issuer": issuer, "algorithm": "SHA1",
        "digits": str(OTP_DIGITS), "period": str(STEP_SECONDS),
    })


def provisioning_qr_data_uri(seed, email):
    """Generate the enrollment QR in-process; never send the seed to a QR API."""
    from io import BytesIO
    import qrcode
    from qrcode.image.pure import PyPNGImage
    image = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6, border=4)
    image.add_data(provisioning_uri(seed, email))
    image.make(fit=True)
    output = BytesIO()
    image.make_image(image_factory=PyPNGImage).save(output)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _cipher():
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY longa obrigatória para proteger autenticação")
    key = HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=b"neuro-diagnosis-saas-v1",
        info=b"mfa:totp-secret-v1",
    ).derive(secret.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def seal_seed(user_id, seed):
    return _cipher().encrypt(f"{int(user_id)}:{seed}".encode("ascii"))


def open_seed(user_id, sealed):
    raw = _cipher().decrypt(bytes(sealed)).decode("ascii")
    prefix, sep, seed = raw.partition(":")
    if sep != ":" or prefix != str(int(user_id)):
        raise ValueError("Chave TOTP não corresponde à conta")
    _seed_bytes(seed)
    return seed


def recovery_codes(number=8):
    if number != 8:
        raise ValueError("Quantidade de recuperação inválida")
    return [secrets.token_hex(10).upper() for _ in range(number)]


def recovery_digest(code):
    if not isinstance(code, str) or len(code) != 20:
        return None
    try:
        token = bytes.fromhex(code)
    except ValueError:
        return None
    return sha256(token).digest()


def token_digest(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 200:
        return None
    try:
        return sha256(token.encode("ascii")).digest()
    except UnicodeEncodeError:
        return None


def agent_digest(agent):
    return sha256((agent or "")[:600].encode("utf-8")).digest()
