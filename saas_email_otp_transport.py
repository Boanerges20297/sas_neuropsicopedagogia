"""Neuro-Diagnosis email OTP transport: intentionally disabled until configured.

No SMTP credentials in source, backups, audit logs, or API responses.
TOTP (6 digits via authenticator) is a separate authentication factor.
"""
from email.message import EmailMessage
import os
import re
import smtplib
import ssl

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_REQUIRED = (
    "NEURO_SMTP_HOST", "NEURO_SMTP_PORT", "NEURO_SMTP_USER",
    "NEURO_SMTP_PASSWORD", "NEURO_SMTP_FROM", "NEURO_SMTP_SECURITY",
)


class EmailOtpUnavailable(RuntimeError):
    """SMTP not activated or unavailable; never silently accept an OTP."""


def is_ready():
    if os.getenv("NEURO_EMAIL_OTP_ENABLED") != "true":
        return False
    if any(not os.getenv(name) for name in _REQUIRED):
        return False
    security = os.getenv("NEURO_SMTP_SECURITY")
    if security not in ("ssl", "starttls"):
        return False
    try:
        port = int(os.environ["NEURO_SMTP_PORT"])
    except (ValueError, TypeError):
        return False
    return 1 <= port <= 65535 and bool(_EMAIL_RE.fullmatch(os.environ["NEURO_SMTP_FROM"]))


def send_code(recipient, code):
    """Send once via authenticated TLS; fail closed with no password/code logs.

    This function is deliberately not wired to the login endpoint until the
    project's dedicated sender account is created and tested.
    """
    if not is_ready():
        raise EmailOtpUnavailable("Envio por e-mail ainda não configurado")
    if not isinstance(recipient, str) or not _EMAIL_RE.fullmatch(recipient):
        raise ValueError("Destinatário inválido")
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{4}", code):
        raise ValueError("Código de e-mail inválido")

    message = EmailMessage()
    message["Subject"] = "Neuro-Diagnosis | Código de acesso"
    message["From"] = os.environ["NEURO_SMTP_FROM"]
    message["To"] = recipient
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(
        "Seu código de verificação é: " + code
        + "\nEle expira em 3 minutos e pode ser usado uma única vez."
        + "\nSe você não solicitou este acesso, ignore a mensagem."
    )
    host = os.environ["NEURO_SMTP_HOST"]
    port = int(os.environ["NEURO_SMTP_PORT"])
    user = os.environ["NEURO_SMTP_USER"]
    password = os.environ["NEURO_SMTP_PASSWORD"]
    context = ssl.create_default_context()
    try:
        if os.environ["NEURO_SMTP_SECURITY"] == "ssl":
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as sender:
                sender.login(user, password)
                sender.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as sender:
                sender.ehlo()
                sender.starttls(context=context)
                sender.ehlo()
                sender.login(user, password)
                sender.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # No exception details: SMTP libraries may embed addresses/credentials.
        raise EmailOtpUnavailable("Falha no envio do código; tente mais tarde") from None
