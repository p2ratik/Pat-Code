from tools.builtins.read_file import ReadFileTool
from tools.builtins.write_file import WriteFileTool

__all__ = ["ReadFileTool"]

def get_all_builtin_tools():
    return [
        ReadFileTool,
        WriteFileTool
    ]


