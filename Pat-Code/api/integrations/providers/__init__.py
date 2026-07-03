from api.integrations.providers.base import BaseProvider
from api.integrations.providers.google import GoogleProvider

_REGISTRY: dict[str, BaseProvider] = {
    "google": GoogleProvider(),
}


def get_provider(name: str) -> BaseProvider:
    """Return the provider instance for the given name; raises KeyError if unknown."""
    provider = _REGISTRY.get(name)
    if not provider:
        raise KeyError(f"Unknown integration provider: '{name}'. Registered: {list(_REGISTRY)}")
    return provider


def get_all_providers() -> dict[str, BaseProvider]:
    """Return the full provider registry dict."""
    return _REGISTRY


__all__ = ["BaseProvider", "GoogleProvider", "get_provider", "get_all_providers"]
