from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    return Fernet(settings.META_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_token(plaintext_token: str) -> str:
    """Encrypt an access token for safe DB storage."""
    return _get_fernet().encrypt(plaintext_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an access token from DB storage. NEVER log the return value."""
    return _get_fernet().decrypt(encrypted_token.encode()).decode()
