from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import (
    Completer,
    Completion,
    merge_completers,
    PathCompleter,
    ThreadedCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

if TYPE_CHECKING:
    from config.config import Config

SLASH_COMMANDS: dict[str, str] = {
    "/help":            "Show available commands",
    "/clear":           "Clear conversation context",
    "/config":          "Show current configuration",
    "/model":           "Change the active model  (/model gpt-4o)",
    "/approval":        "Set approval policy  (auto | on-request | always)",
    "/tools":           "List all available tools",
    "/mcp":             "Show MCP server status",
    "/stats":           "Show session statistics",
    "/save":            "Save the current session",
    "/sessions":        "List all saved sessions",
    "/resume":          "Resume a saved session  (/resume <id>)",
    "/checkpoint":      "Create a checkpoint snapshot",
    "/listcheckpoints": "List checkpoints for this session",
    "/restore":         "Restore from a checkpoint  (/restore <id>)",
    "/exit":            "Exit PAT",
    "/quit":            "Exit PAT (alias)",
}

_PASTE_MIN_CHARS = 80


def _sanitize(text: str) -> str:
    """Strip lone surrogates that would break UTF-8 encoding downstream."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


class SlashCommandCompleter(Completer):
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        stripped = document.text_before_cursor.lstrip()
        if not stripped.startswith("/") or " " in stripped:
            return
        for cmd, desc in SLASH_COMMANDS.items():
            if cmd.startswith(stripped):
                yield Completion(cmd, start_position=-len(stripped), display=cmd, display_meta=desc)


class AtMentionCompleter(Completer):
    def __init__(self, cwd: str | Path):
        self._path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        text = document.text_before_cursor
        at = text.rfind("@")
        if at == -1:
            return
        after = text[at + 1:]
        if " " in after:
            return
        fake = Document(after, cursor_position=len(after))
        for c in self._path_completer.get_completions(fake, complete_event):
            yield Completion(c.text, start_position=c.start_position, display=c.display, display_meta=c.display_meta)


PAT_STYLE = Style.from_dict(
    {
        "prompt.arrow":                             "#38bdf8 bold",
        "completion-menu":                          "bg:#0f172a #cbd5e1",
        "completion-menu.completion":               "bg:#0f172a #cbd5e1",
        "completion-menu.completion.current":       "bg:#1e3a5f #f8fafc bold",
        "completion-menu.meta.completion":          "bg:#0f172a #475569",
        "completion-menu.meta.completion.current":  "bg:#1e3a5f #94a3b8",
        "scrollbar.background":                     "bg:#1e293b",
        "scrollbar.button":                         "bg:#38bdf8",
        "auto-suggest":                             "#334155",
        "bottom-toolbar":                           "bg:#0f172a",
        "":                                         "bg:#0a0f1a #f8fafc",
    }
)

PROMPT_MESSAGE = [("class:prompt.arrow", "> ")]


def _make_toolbar(config: "Config"):
    def _toolbar() -> HTML:
        model = getattr(config, "model_name", "")
        parts = Path(str(getattr(config, "cwd", "."))).parts
        short_cwd = str(Path(*parts[-2:])) if len(parts) >= 2 else str(getattr(config, "cwd", "."))
        return HTML(
            f"<style bg='#1e293b' fg='#38bdf8'> PAT </style>"
            f"<style bg='#1e293b' fg='#334155'>|</style>"
            f"<style bg='#1e293b' fg='#7dd3fc'> model: </style>"
            f"<style bg='#1e293b' fg='#f8fafc'>{model}</style>"
            f"<style bg='#1e293b' fg='#334155'> | </style>"
            f"<style bg='#1e293b' fg='#7dd3fc'>cwd: </style>"
            f"<style bg='#1e293b' fg='#94a3b8'>{short_cwd}</style>"
            f"<style bg='#1e293b' fg='#334155'>  |  </style>"
            f"<style bg='#1e293b' fg='#475569'>Tab complete  |  Alt+Enter newline  |  Ctrl+L clear  |  /help</style>"
            f"<style bg='#1e293b' fg='#334155'> </style>"
        )
    return _toolbar


class PatPromptSession:
    """Wraps PromptSession with paste interception and surrogate sanitization."""

    def __init__(self, config: "Config"):
        self._paste_buffer: str | None = None
        self._session = self._build(config)

    def _build(self, config: "Config") -> PromptSession:
        history_dir = Path.home() / ".pat"
        history_dir.mkdir(parents=True, exist_ok=True)

        kb = self._make_key_bindings()
        completer = merge_completers([
            SlashCommandCompleter(),
            ThreadedCompleter(AtMentionCompleter(config.cwd)),
        ])

        return PromptSession(
            history=FileHistory(str(history_dir / "history")),
            completer=completer,
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
            style=PAT_STYLE,
            bottom_toolbar=_make_toolbar(config),
            complete_while_typing=True,
            mouse_support=False,
            wrap_lines=True,
            vi_mode=False,
        )

    def _make_key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("c-l")
        def _clear(event):
            os.system("cls" if os.name == "nt" else "clear")
            event.app.renderer.reset()

        @kb.add("escape", "enter")
        def _newline(event):
            event.current_buffer.insert_text("\n")

        @kb.add(Keys.BracketedPaste)
        def _paste(event):
            text = _sanitize(event.data)
            is_large = len(text) >= _PASTE_MIN_CHARS or "\n" in text
            if is_large:
                self._paste_buffer = text
                lines = text.count("\n") + 1
                chars = len(text)
                event.current_buffer.reset()
                event.current_buffer.insert_text(f"[Pasted {lines} lines · {chars} chars]")
            else:
                event.current_buffer.insert_text(text)

        return kb

    async def prompt_async(self, message, **kwargs) -> str:
        raw = await self._session.prompt_async(message, **kwargs)

        if self._paste_buffer is not None:
            content = self._paste_buffer
            self._paste_buffer = None
            return content

        return _sanitize(raw or "")
