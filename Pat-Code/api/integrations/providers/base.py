import abc
from typing import Any
import httpx


class BaseProvider(abc.ABC):
    """Knows how to build an authenticated client and manage tokens for one provider."""

    name: str = ""

    @abc.abstractmethod
    async def build_client(self, access_token: str) -> httpx.AsyncClient:
        """Return an httpx.AsyncClient pre-configured with the provider's auth headers."""
        pass

    @abc.abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Exchange an authorization code for tokens. Returns the raw token response dict."""
        pass

    @abc.abstractmethod
    async def refresh_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Exchange a refresh token for a new access token. Returns the raw token response dict."""
        pass

    @abc.abstractmethod
    async def revoke_token(self, token: str, client_id: str, client_secret: str) -> bool:
        """Revoke an access or refresh token. Returns True if revocation succeeded."""
        pass

    def build_auth_url(
        self,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        state: str,
    ) -> str:
        """Build the provider's authorization URL for the OAuth redirect."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement build_auth_url")
