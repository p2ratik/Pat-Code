from rich.console import Console

from config.config import Config
from ui.tui1 import AGENT_THEME, TUI as ActiveTUI, get_console


class TUI(ActiveTUI):
    def __init__(self, config: Config, console: Console | None = None) -> None:
        super().__init__(console or get_console(), config)
