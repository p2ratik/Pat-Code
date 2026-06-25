"""
Token encryption helpers for mcp_credentials.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
Key must be a 32-byte URL-safe base64 string in MCP_ENCRYPTION_KEY env var.
Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import os
import base64
from cryptography.fernet import Fernet, InvalidToken


def _load_fernet() -> Fernet:
    raw = os.environ.get("MCP_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "MCP_ENCRYPTION_KEY env var is required for OAuth token storage. "
            "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(raw.encode())


# Module-level singleton — fails fast at import if key is missing.
_fernet = _load_fernet()


def encrypt_token(plaintext: str) -> str:
    """Return a URL-safe base64 Fernet ciphertext string."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext; raises InvalidToken on tamper/wrong key."""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Token decryption failed — key mismatch or data corrupted") from exc
