"""Sensitive professional identity fields, validation and MySQL profile persistence.

CPF is encrypted at rest with a separate HKDF-derived Fernet key; uniqueness is
enforced by an HMAC digest. No CPF/password is included in audit records.
"""
from datetime import date
from hashlib import sha256
import base64
import hmac
import os
import re

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

AREAS = {
    "psicologia": "Psicologia",
    "neuropsicopedagogia": "Neuropsicopedagogia",
    "psiquiatria": "Psiquiatria",
    "psicopedagogia": "Psicopedagogia",
}
LEGACY_AREA = {
    "psicologia": "psicologo",
    "neuropsicopedagogia": "neuropsicopedagogo",
    "psiquiatria": "outro",
    "psicopedagogia": "outro",
}


def _secret(purpose):
    key = os.getenv("SECRET_KEY", "")
    if len(key) < 32:
        raise RuntimeError("SECRET_KEY obrigatória para proteger dados profissionais")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"neuro-diagnosis-saas-v1",
                info=("profile:" + purpose).encode()).derive(key.encode())


def validate_cpf(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValueError("CPF inválido")
    for count in (9, 10):
        total = sum(int(digits[i]) * (count + 1 - i) for i in range(count))
        check = (total * 10) % 11
        if (0 if check == 10 else check) != int(digits[count]):
            raise ValueError("CPF inválido")
    return digits


def masked_cpf(ciphertext):
    if not ciphertext:
        return "Não informado"
    cpf = Fernet(base64.urlsafe_b64encode(_secret("cpf-encryption"))).decrypt(
        bytes(ciphertext)).decode("ascii")
    return "***.***." + cpf[6:9] + "-" + cpf[9:]


def prepare_cpf(value):
    digits = validate_cpf(value)
    fingerprint = hmac.new(_secret("cpf-lookup"), digits.encode(), sha256).hexdigest()
    encrypted = Fernet(base64.urlsafe_b64encode(_secret("cpf-encryption"))).encrypt(
        digits.encode())
    return fingerprint, encrypted


def validate_birth_date(value):
    try:
        birth = date.fromisoformat((value or "").strip())
    except (ValueError, TypeError):
        raise ValueError("Data de nascimento inválida") from None
    today = date.today()
    if birth > today or birth.year < today.year - 120:
        raise ValueError("Data de nascimento fora do intervalo permitido")
    return birth


def validate_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) not in (10, 11) or digits[:2] == "00" or digits[0] == "0":
        raise ValueError("Telefone inválido: informe DDD e número")
    return digits


def validate_area(value):
    if value not in AREAS:
        raise ValueError("Selecione uma área de atuação válida")
    return value


def validate_details(cpf, area, birth_date, phone):
    practice_area = validate_area(area)
    digest, encrypted = prepare_cpf(cpf)
    birth = validate_birth_date(birth_date)
    telephone = validate_phone(phone)
    return {"practice_area": practice_area, "cpf_digest": digest,
            "cpf_encrypted": encrypted, "birth_date": birth, "phone": telephone}


def phone_display(digits):
    if not digits:
        return ""
    digits = str(digits)
    return f"({digits[:2]}) {digits[2:-4]}-{digits[-4:]}"
