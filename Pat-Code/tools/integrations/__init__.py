"""Integration tool discovery — returns all OAuthTool subclasses for seeding and runtime injection."""
from tools.integrations.google.read_sheet import ReadGoogleSheetTool
from tools.integrations.google.append_rows import AppendGoogleSheetRowsTool


def get_all_integration_tools() -> list[type]:
    """Return every registered OAuthTool class."""
    return [
        ReadGoogleSheetTool,
        AppendGoogleSheetRowsTool,
    ]
