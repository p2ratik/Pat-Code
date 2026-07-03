class IntegrationError(Exception):
    """Base for all integration platform errors."""


class AuthorizationRequiredError(IntegrationError):
    """Raised when a user has no connection to the requested provider."""

    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"User has not connected provider '{provider}'")


class TokenExpiredError(IntegrationError):
    """Raised when the access token is expired and the refresh attempt failed."""

    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Token for provider '{provider}' is expired and could not be refreshed")


class InsufficientScopesError(IntegrationError):
    """Raised when the granted scopes do not cover what the tool requires."""

    def __init__(self, provider: str, missing_scopes: list[str]):
        self.provider = provider
        self.missing_scopes = missing_scopes
        super().__init__(
            f"Provider '{provider}' is missing required scopes: {missing_scopes}"
        )


class ProviderNotEnabledError(IntegrationError):
    """Raised when the requested provider is registered but disabled."""

    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Integration provider '{provider}' is disabled")
