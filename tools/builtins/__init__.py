from tools.builtins.edit_file import EditTool
from tools.builtins.glob import GlobTool
from tools.builtins.grep import GrepTool
from tools.builtins.list_dir import ListDirTool
from tools.builtins.memory import MemoryTool
from tools.builtins.read_file import ReadFileTool
from tools.builtins.shell import ShellTool
from tools.builtins.todo import TodosTool
from tools.builtins.web_fetch import WebFetchTool
from tools.builtins.web_search import WebSearchTool
from tools.builtins.write_file import WriteFileTool
from apply_patch import ApplyPatchTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
    "WebFetchTool",
    "TodosTool",
    "MemoryTool",
    "ApplyPatchTool",
]


def get_all_builtin_tools() -> list[type]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
        WebFetchTool,
        TodosTool,
        MemoryTool,
        ApplyPatchTool,
    ]