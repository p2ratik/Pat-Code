from typing import Any
from urllib.parse import urlencode

import httpx

from api.integrations.providers.base import BaseProvider


class GoogleProvider(BaseProvider):
    name = "google"

    _AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"
    _REVOKE_URL = "https://oauth2.googleapis.com/revoke"

    def build_auth_url(
        self,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        state: str,
    ) -> str:
        """Constructs the Google OAuth2 consent URL with offline access for refresh tokens."""
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self._AUTH_URL}?{urlencode(params)}"

    async def build_client(self, access_token: str) -> httpx.AsyncClient:
        """Returns an httpx client with a Bearer authorization header for the Google APIs."""
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Exchanges an authorization code for access + refresh tokens at Google's token endpoint."""
        async with httpx.AsyncClient(timeout=15.0) as http:
            response = await http.post(
                self._TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Exchanges a refresh token for a new access token using client_secret_post."""
        async with httpx.AsyncClient(timeout=15.0) as http:
            response = await http.post(
                self._TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def revoke_token(self, token: str, client_id: str, client_secret: str) -> bool:
        """Calls Google's revoke endpoint; returns True on success, False on any error."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                response = await http.post(
                    self._REVOKE_URL,
                    params={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                return response.status_code == 200
        except Exception:
            return False
