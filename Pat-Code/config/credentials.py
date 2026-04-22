"""
Secure credential storage via the OS keyring (Windows Credential Manager,
macOS Keychain, Linux Secret Service / KWallet).

Usage:
    set_credential("apikey", "sk-...")
    get_credential("apikey")          -> "sk-..." or None
    delete_credential("apikey")
"""

import keyring

# All secrets are stored under this keyring service name.
_SERVICE = "ai-agent"

# Canonical key names stored in the keyring.
APIKEY_KEY  = "apikey"
BASEURL_KEY = "baseurl"


def set_credential(name: str, value: str) -> None:
    """Persist *value* under *name* in the OS keyring."""
    keyring.set_password(_SERVICE, name, value)


def get_credential(name: str) -> str | None:
    """Return the stored credential or *None* if not set."""
    return keyring.get_password(_SERVICE, name)


def delete_credential(name: str) -> bool:
    """Delete a stored credential.  Returns True if it existed."""
    try:
        keyring.delete_password(_SERVICE, name)
        return True
    except keyring.errors.PasswordDeleteError:
        return False
