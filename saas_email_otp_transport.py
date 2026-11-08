"""Gmail OTP transport; encrypted DB credential from the superadmin setup page.

Fail-closed: no configured/tested provider -> no OTP email. SMTP
exceptions are sanitized; no code, credential or recipient is logged.
"""
from email.message import EmailMessage
import os
import re
import smtplib
import ssl

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class EmailOtpUnavailable(RuntimeError):
    pass


def _environment_config():
    required = ("NEURO_SMTP_HOST","NEURO_SMTP_PORT","NEURO_SMTP_USER",
                "NEURO_SMTP_PASSWORD","NEURO_SMTP_FROM","NEURO_SMTP_SECURITY")
    if os.getenv("NEURO_EMAIL_OTP_ENABLED") != "true":
        return None
    if any(not os.getenv(name) for name in required):
        return None
    if os.getenv("NEURO_SMTP_SECURITY") not in ("ssl","starttls"):
        return None
    try:
        port=int(os.environ["NEURO_SMTP_PORT"])
    except (TypeError,ValueError):
        return None
    if not 1<=port<=65535 or not _EMAIL_RE.fullmatch(os.environ["NEURO_SMTP_FROM"]):
        return None
    return {"host":os.environ["NEURO_SMTP_HOST"],"port":port,
            "user":os.environ["NEURO_SMTP_USER"],
            "password":os.environ["NEURO_SMTP_PASSWORD"],
            "from":os.environ["NEURO_SMTP_FROM"],
            "security":os.environ["NEURO_SMTP_SECURITY"]}


def _configuration():
    if os.getenv("NEURO_SMTP_WEB_CONFIG_ENABLED","false").lower()=="true":
        try:
            import saas_smtp_settings as settings
            return settings.active_transport()
        except Exception:
            # Never downgrade a failed encrypted-credential lookup to an
            # unverified plaintext environment credential.
            return None
    return _environment_config()


def is_ready():
    return bool(_configuration())


def _send(config, recipient, message_body, subject):
    if not isinstance(recipient,str) or not _EMAIL_RE.fullmatch(recipient):
        raise ValueError("Destinatário inválido")
    msg=EmailMessage()
    msg["Subject"]=subject
    msg["From"]=config["from"]
    msg["To"]=recipient
    msg["Auto-Submitted"]="auto-generated"
    msg.set_content(message_body)
    context=ssl.create_default_context()
    try:
        if config["security"]=="ssl":
            with smtplib.SMTP_SSL(config["host"],config["port"],timeout=10,context=context) as smtp:
                smtp.login(config["user"],config["password"])
                smtp.send_message(msg)
        elif config["security"]=="starttls":
            with smtplib.SMTP(config["host"],config["port"],timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(config["user"],config["password"])
                smtp.send_message(msg)
        else:
            raise EmailOtpUnavailable("Configuração SMTP inválida")
    except (smtplib.SMTPException,OSError,ValueError):
        raise EmailOtpUnavailable("Envio SMTP indisponível") from None


def send_code(recipient, code):
    config=_configuration()
    if not config:
        raise EmailOtpUnavailable("Envio por e-mail não configurado")
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{4}",code):
        raise ValueError("Código inválido")
    _send(config,recipient,
          "Seu código de recuperação é: "+code+
          "\nExpira em 3 minutos e funciona apenas uma vez."+
          "\nSe não solicitou, ignore esta mensagem.",
          "Neuro-Diagnosis | Recuperação de senha")


def send_verification_code(recipient, code):
    """Email proof differs from password recovery: six digits, ten minutes."""
    config = _configuration()
    if not config:
        raise EmailOtpUnavailable("Verificacao por e-mail indisponivel")
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{6}",code):
        raise ValueError("Codigo invalido")
    _send(config,recipient,
          "Seu codigo de verificacao Neuro-Diagnosis e: "+code+
          "\nExpira em 10 minutos, funciona uma vez e nao deve ser compartilhado."+
          "\nSe nao solicitou cadastro ou alteracao de e-mail, ignore.",
          "Neuro-Diagnosis | Confirmacao de e-mail")


def send_setup_test(code):
    """Send exclusively to the fixed sender's mailbox, not arbitrary addresses."""
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{6}",code):
        raise ValueError("Código de teste inválido")
    import saas_smtp_settings as settings
    config=settings.draft_transport()
    if not config:
        raise EmailOtpUnavailable("Senha de app ainda não cadastrada")
    _send(config,settings.SENDER,
          "Código para ativar o e-mail de recuperação do Neuro-Diagnosis: "+code+
          "\nExpira em 10 minutos. Nunca envie este código a terceiros.",
          "Neuro-Diagnosis | Verificação do remetente")
