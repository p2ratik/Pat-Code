from tools.builtins.read_file import ReadFileTool
from tools.builtins.write_file import WriteFileTool
from tools.builtins.edit_file import EditTool

__all__ = ["ReadFileTool"]

def get_all_builtin_tools():
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool

    ]


