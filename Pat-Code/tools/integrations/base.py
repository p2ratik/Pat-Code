"""OAuthTool — stateless base class for all integration tools.

Resolves user_id + credential_manager from invocation.session (the runtime),
then delegates to run() which subclasses implement.
"""
import abc
import httpx

from tools.base import Tool, ToolInvocation, Toolkind, ToolResult
from api.integrations.exceptions import (
    AuthorizationRequiredError,
    InsufficientScopesError,
    TokenExpiredError,
    ProviderNotEnabledError,
)


class OAuthTool(Tool):
    """Stateless base for all integration (OAuth2-backed) tools."""

    provider_name: str = ""
    required_scopes: list[str] = []
    kind = Toolkind.INTEGRATION

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Resolve auth via CredentialManager then hand off to run()."""
        runtime = invocation.session
        user_id = getattr(runtime, "user_id", None)
        if not user_id:
            return ToolResult.error_result(
                "Integration tools require an authenticated user session.",
                metadata={"requires_auth": True, "provider": self.provider_name},
            )

        credential_manager = getattr(runtime, "credential_manager", None)
        if not credential_manager:
            return ToolResult.error_result(
                "No credential manager available in this runtime.",
                metadata={"provider": self.provider_name},
            )

        try:
            client = await credential_manager.get_client(
                provider=self.provider_name,
                user_id=user_id,
                scopes=self.required_scopes,
            )
        except AuthorizationRequiredError:
            return ToolResult.error_result(
                f"You haven't connected {self.provider_name}. "
                "Go to Settings → Integrations to connect.",
                metadata={"requires_auth": True, "provider": self.provider_name},
            )
        except InsufficientScopesError as exc:
            return ToolResult.error_result(
                f"Insufficient permissions for {self.provider_name}. "
                f"Missing: {exc.missing_scopes}. Please reconnect with wider permissions.",
                metadata={
                    "requires_reauth": True,
                    "provider": self.provider_name,
                    "missing_scopes": exc.missing_scopes,
                },
            )
        except TokenExpiredError:
            return ToolResult.error_result(
                f"Your {self.provider_name} session has expired. "
                "Please reconnect via Settings → Integrations.",
                metadata={"requires_reauth": True, "provider": self.provider_name},
            )
        except ProviderNotEnabledError:
            return ToolResult.error_result(
                f"The {self.provider_name} integration is currently disabled by the administrator.",
                metadata={"provider": self.provider_name},
            )

        async with client:
            return await self.run(client, invocation)

    @abc.abstractmethod
    async def run(self, client: httpx.AsyncClient, invocation: ToolInvocation) -> ToolResult:
        """Execute the actual API call. client is a pre-authenticated httpx.AsyncClient."""
        pass
