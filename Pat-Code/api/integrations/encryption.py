import os
from cryptography.fernet import Fernet, InvalidToken


def _load_fernet() -> Fernet:
    raw = os.environ.get("INTEGRATION_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "INTEGRATION_ENCRYPTION_KEY env var is required for integration token storage. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(raw.encode())


_fernet = _load_fernet()


def encrypt_token(plaintext: str) -> str:
    """Return a URL-safe base64 Fernet ciphertext string."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext; raises ValueError on tamper or wrong key."""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Integration token decryption failed — key mismatch or data corrupted") from exc
