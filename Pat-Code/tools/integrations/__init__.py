from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.integrations.base import OAuthTool


def get_all_integration_tools() -> list[type]:
    """Return all registered OAuthTool subclasses for seeding and runtime injection."""
    return []
