import os
from dotenv import load_dotenv

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except Exception:
    Fernet = None
    CRYPTO_AVAILABLE = False

load_dotenv()


def get_encryption_key():
    """Busca a chave no .env ou gera uma nova automaticamente."""
    if not CRYPTO_AVAILABLE:
        return b""

    key = os.getenv("FIELD_ENCRYPTION_KEY")
    if not key:
        new_key = Fernet.generate_key().decode("utf-8")
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "FIELD_ENCRYPTION_KEY" not in content:
                    with open(env_path, "a", encoding="utf-8") as f:
                        f.write(f"\nFIELD_ENCRYPTION_KEY={new_key}\n")
            else:
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(f"FIELD_ENCRYPTION_KEY={new_key}\n")
            key = new_key
        except Exception:
            key = new_key
    return key.encode("utf-8")


if CRYPTO_AVAILABLE:
    try:
        _key = get_encryption_key()
        fernet = Fernet(_key)
    except Exception:
        _key = Fernet.generate_key()
        fernet = Fernet(_key)
else:
    fernet = None
    print("[WARNING] cryptography indisponivel no ambiente local; criptografia em modo bypass.")


def encrypt_data(text):
    if not text:
        return ""
    if not CRYPTO_AVAILABLE or not fernet:
        return text
    try:
        return fernet.encrypt(text.encode("utf-8")).decode("utf-8")
    except Exception:
        return text


def decrypt_data(cipher_text):
    if not cipher_text:
        return ""
    if not CRYPTO_AVAILABLE or not fernet:
        return cipher_text
    try:
        return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return cipher_text
