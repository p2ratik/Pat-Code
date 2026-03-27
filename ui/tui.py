from pathlib import Path
from typing import Any
from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt
from rich.console import Group
from rich.syntax import Syntax
from rich.markdown import Markdown
# from config.config import Config
# from tools.base import ToolConfirmation
# from utils.paths import display_path_rel_to_cwd
import re

AGENT_THEME = Theme(
    {
        # General
        "info": "cyan",
        "warning": "yellow",
        "error": "bright_red bold",
        "success": "green",
        "dim": "dim",
        "muted": "grey50",
        "border": "grey35",
        "highlight": "bold cyan",
        # Roles
        "user": "bright_blue bold",
        "assistant": "bright_white",
        # Tools
        "tool": "bright_magenta bold",
        "tool.read": "cyan",
        "tool.write": "yellow",
        "tool.shell": "magenta",
        "tool.network": "bright_blue",
        "tool.memory": "green",
        "tool.mcp": "bright_cyan",
        # Code / blocks
        "code": "white",
    }
)

_console: Console | None = None

def get_console()->Console:
    global _console
    if _console is None:
        _console = Console(theme = AGENT_THEME, highlight=False)

    return _console

class TUI:
    def __init__(self, _console):
        self.console = _console
        #self._assistant_stream_open = False

    def stream_assistant_delta(self, content):
        self.console.print(content, end="", markup=False)    

    def begin_assistant(self)-> None:
        self.console.print()
        self.console.print(Rule(Text("assistant", style="assistant")))
        #self._assistant_stream_open = True

    def end_assistant(self):
        self.console.print()

        