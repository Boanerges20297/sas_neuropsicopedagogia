"""Consistent credential strength rules for Neuro-Diagnosis."""
import secrets
import string

MIN_LENGTH = 8
MAX_LENGTH = 128
MIN_LETTERS = 2
MIN_NUMBERS = 4
MIN_SYMBOLS = 1
ALPHABET = string.ascii_letters + string.digits + "!@#$%&*-_"


def valid_credential(value):
    return (
        isinstance(value, str)
        and MIN_LENGTH <= len(value) <= MAX_LENGTH
        and sum(c.isalpha() for c in value) >= MIN_LETTERS
        and sum(c.isdigit() for c in value) >= MIN_NUMBERS
        and sum(not c.isalnum() and not c.isspace() for c in value) >= MIN_SYMBOLS
    )


def requirement():
    return "Use senha de 8 a 128 caracteres, com pelo menos 2 letras, 4 números e 1 símbolo."


def temporary_credential():
    """Generate 20 randomized characters, including all mandatory categories."""
    chars = [
        *(secrets.choice(string.ascii_letters) for _ in range(MIN_LETTERS)),
        *(secrets.choice(string.digits) for _ in range(MIN_NUMBERS)),
        secrets.choice("!@#$%&*-_"),
        *(secrets.choice(ALPHABET) for _ in range(13)),
    ]
    secrets.SystemRandom().shuffle(chars)
    value = "".join(chars)
    assert valid_credential(value)
    return value
