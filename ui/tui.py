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
from rich.padding import Padding
from rich.columns import Columns
from rich.align import Align
from config.config import Config
from tools.base import ToolConfirmation
from utils.paths import display_path_rel_to_cwd
from utils.text import truncate_text
import re

# ── Theme ──────────────────────────────────────────────────────────────────────
# Palette: near-black bg, cool slate text, ice-blue accents, amber warnings
AGENT_THEME = Theme(
    {
        # General
        "info":      "bold #7dd3fc",          # sky-300
        "warning":   "bold #fbbf24",          # amber-400
        "error":     "bold #f87171",          # red-400
        "success":   "bold #34d399",          # emerald-400
        "dim":       "dim",
        "muted":     "#64748b",               # slate-500
        "border":    "#334155",               # slate-700
        "highlight": "bold #7dd3fc",

        # Roles
        "user":      "bold #38bdf8",          # sky-400
        "assistant": "#e2e8f0",              # slate-200

        # Tools — each kind gets its own cool hue
        "tool":          "bold #94a3b8",      # slate-400  (default)
        "tool.read":     "#67e8f9",           # cyan-300
        "tool.write":    "#fcd34d",           # amber-300
        "tool.shell":    "#c4b5fd",           # violet-300
        "tool.network":  "#93c5fd",           # blue-300
        "tool.memory":   "#86efac",           # green-300
        "tool.mcp":      "#67e8f9",           # cyan-300

        # Code
        "code":          "#cbd5e1",           # slate-300

        # Decoration
        "accent":        "#0ea5e9",           # sky-500
        "tag":           "#475569",           # slate-600
    }
)

# Box styles — use MINIMAL for subtle structure, ROUNDED for panels
_PANEL_BOX   = box.ROUNDED
_TABLE_BOX   = box.SIMPLE_HEAD

_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    return _console


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tool_icon(tool_kind: str | None) -> str:
    return {
        "read":    "○",
        "write":   "◈",
        "shell":   "❯",
        "network": "◎",
        "memory":  "◇",
        "mcp":     "◉",
    }.get(tool_kind or "", "◆")


def _tool_border(tool_kind: str | None) -> str:
    return f"tool.{tool_kind}" if tool_kind else "tool"


def _divider(label: str = "", style: str = "border") -> Rule:
    if label:
        return Rule(Text(f" {label} ", style="muted"), style=style)
    return Rule(style=style)


# ── TUI ────────────────────────────────────────────────────────────────────────

class TUI:
    def __init__(self, _console: Console, config: Config):
        self.console = _console
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self._max_block_tokens = 2500
        self.cwd = config.cwd
        self.config = config

    # ── Streaming ─────────────────────────────────────────────────────────────

    def stream_assistant_delta(self, content: str) -> None:
        self.console.print(content, end="", markup=False)

    def begin_assistant(self) -> None:
        self.console.print()
        self.console.print(
            Rule(
                Text("  assistant  ", style="bold #0ea5e9 on #0c1929"),
                style="border",
                align="left",
            )
        )
        self.console.print()

    def end_assistant(self) -> None:
        self.console.print()
        self.console.print(Rule(style="#1e293b"))

    def show_help(self) -> None:
        help_lines = [
            "/help - Show this help",
            "/clear - Clear conversation context",
            "/config - Show current configuration",
            "/model <name> - Change model name",
            "/approval <policy> - Set approval policy",
            "/tools - List available tools",
            "/mcp - Show MCP server status",
            "/stats - Show session statistics",
            "/save - Save current session",
            "/sessions - List saved sessions",
            "/resume <session_id> - Resume a saved session",
            "/checkpoint - Create a checkpoint",
            "/restore <checkpoint_id> - Restore from checkpoint",
            "/exit or /quit - Exit the CLI",
        ]

        body = Text("\n".join(f"  {line}" for line in help_lines), style="assistant")
        self.console.print()
        self.console.print(
            Panel(
                body,
                title=Text(" Commands ", style="bold info"),
                title_align="left",
                border_style="border",
                box=_PANEL_BOX,
                padding=(0, 1),
            )
        )

    # ── Argument ordering ─────────────────────────────────────────────────────

    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[tuple]:
        _PREFERRED_ORDER = {
            "read_file":  ["path", "offset", "limit"],
            "write_file": ["path", "create_directories", "content"],
            "edit":       ["path", "replace_all", "old_string", "new_string"],
            "shell":      ["command", "timeout", "cwd"],
            "list_dir":   ["path", "include_hidden"],
            "grep":       ["path", "case_insensitive", "pattern"],
            "glob":       ["path", "pattern"],
            "todos":      ["id", "action", "content"],
            "memory":     ["action", "key", "value"],
        }
        preferred = _PREFERRED_ORDER.get(tool_name, [])
        ordered: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for key in preferred:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
        ordered.extend((k, v) for k, v in args.items() if k not in seen)
        return ordered

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="muted", justify="right", no_wrap=True, min_width=12)
        table.add_column(style="code", overflow="fold")

        for key, value in self._ordered_args(tool_name, args):
            if isinstance(value, str) and key in {"content", "old_string", "new_string"}:
                lines = len(value.splitlines()) or 0
                size  = len(value.encode("utf-8", errors="replace"))
                value = f"‹{lines} lines · {size} B›"
            if not isinstance(value, str):
                value = str(value)
            table.add_row(f"{key}", value)

        return table

    # ── Tool call start ────────────────────────────────────────────────────────

    def tool_call_start(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        arguments: dict[str, Any],
    ) -> None:
        self._tool_args_by_call_id[call_id] = arguments
        border_style = _tool_border(tool_kind)
        icon         = _tool_icon(tool_kind)

        title = Text.assemble(
            (f" {icon}  ", border_style),
            (name, f"bold {border_style}"),
            ("   ", "muted"),
            (f"#{call_id[:7]}", "muted"),
        )

        display_args = dict(arguments)
        for key in ("path", "cwd"):
            val = display_args.get(key)
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(display_path_rel_to_cwd(val, self.cwd))

        body = (
            self._render_args_table(name, display_args)
            if display_args
            else Text("no arguments", style="muted")
        )

        self.console.print()
        self.console.print(
            Panel(
                body,
                title=title,
                title_align="left",
                subtitle=Text(" running ", style="muted"),
                subtitle_align="right",
                border_style=border_style,
                box=_PANEL_BOX,
                padding=(0, 2),
            )
        )

    # ── Tool call complete ─────────────────────────────────────────────────────

    def _extract_read_file_code(self, text: str) -> tuple[int, str] | None:
        body = text
        header_match = re.match(r"^Showing lines (\d+)-(\d+) of (\d+)\n\n", text)
        if header_match:
            body = text[header_match.end():]
        code_lines: list[str] = []
        start_line: int | None = None
        for line in body.splitlines():
            m = re.match(r"^\s*(\d+)\|(.*)$", line)
            if not m:
                return None
            line_no = int(m.group(1))
            if start_line is None:
                start_line = line_no
            code_lines.append(m.group(2))
        if start_line is None:
            return None
        return start_line, "\n".join(code_lines)

    def _guess_language(self, path: str | None) -> str:
        if not path:
            return "text"
        return {
            ".py": "python", ".js": "javascript", ".jsx": "jsx",
            ".ts": "typescript", ".tsx": "tsx", ".json": "json",
            ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
            ".md": "markdown", ".sh": "bash", ".bash": "bash",
            ".zsh": "bash", ".rs": "rust", ".go": "go",
            ".java": "java", ".kt": "kotlin", ".swift": "swift",
            ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
            ".css": "css", ".html": "html", ".xml": "xml", ".sql": "sql",
        }.get(Path(path).suffix.lower(), "text")

    def _meta_text(self, *parts: str) -> Text:
        """Render a dimmed metadata line like  path • lines 1-40 of 200"""
        t = Text(style="muted")
        for i, part in enumerate(parts):
            if i:
                t.append("  ·  ")
            t.append(part)
        return t

    def tool_call_complete(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        success: bool,
        output: str,
        error: str | None,
        metadata: dict[str, Any] | None,
        diff: str | None,
        truncated: bool,
        exit_code: int | None,
    ) -> None:
        border_style = _tool_border(tool_kind)
        icon         = _tool_icon(tool_kind)
        ok           = success

        status_char  = "✓" if ok else "✗"
        status_style = "success" if ok else "error"

        title = Text.assemble(
            (f" {status_char}  ", status_style),
            (name, f"bold {border_style}"),
            ("   ", "muted"),
            (f"#{call_id[:7]}", "muted"),
        )

        args         = self._tool_args_by_call_id.get(call_id, {})
        primary_path = (metadata or {}).get("path") if isinstance(metadata, dict) else None
        blocks: list  = []

        # ── read_file ──────────────────────────────────────────────────────────
        if name == "read_file" and ok:
            if primary_path:
                parsed = self._extract_read_file_code(output)
                if parsed:
                    start_line, code = parsed
                    shown_start  = (metadata or {}).get("shown_start")
                    shown_end    = (metadata or {}).get("shown_end")
                    total_lines  = (metadata or {}).get("total_lines")
                    meta_parts   = [str(display_path_rel_to_cwd(primary_path, self.cwd))]
                    if shown_start and shown_end and total_lines:
                        meta_parts.append(f"lines {shown_start}–{shown_end} of {total_lines}")
                    blocks.append(self._meta_text(*meta_parts))
                    blocks.append(
                        Syntax(
                            code,
                            self._guess_language(primary_path),
                            theme="one-dark",
                            line_numbers=True,
                            start_line=start_line,
                            word_wrap=False,
                        )
                    )
                else:
                    blocks.append(
                        Syntax(
                            truncate_text(output, self.config.model_name, self._max_block_tokens),
                            self._guess_language(primary_path),
                            theme="one-dark",
                            word_wrap=True,
                        )
                    )
            else:
                blocks.append(
                    Syntax(
                        truncate_text(output, "", self._max_block_tokens),
                        "text", theme="one-dark", word_wrap=False,
                    )
                )

        # ── write_file / edit ──────────────────────────────────────────────────
        elif name in {"write_file", "edit"} and ok and diff:
            msg = output.strip() or "Done"
            blocks.append(Text(f"  {msg}", style="muted"))
            blocks.append(
                Syntax(
                    truncate_text(diff, self.config.model_name, self._max_block_tokens),
                    "diff", theme="one-dark", word_wrap=True,
                )
            )

        # ── shell ──────────────────────────────────────────────────────────────
        elif name == "shell" and ok:
            command = args.get("command", "")
            if isinstance(command, str) and command.strip():
                blocks.append(Text(f"  ❯  {command.strip()}", style="muted"))
            if exit_code is not None:
                exit_style = "success" if exit_code == 0 else "error"
                blocks.append(Text(f"  exit {exit_code}", style=exit_style))
            blocks.append(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text", theme="one-dark", word_wrap=True,
                )
            )

        # ── web_search ─────────────────────────────────────────────────────────
        elif name == "web_search" and ok:
            results = (metadata or {}).get("results")
            query   = args.get("query", "")
            parts   = []
            if isinstance(query, str) and query:
                parts.append(query)
            if isinstance(results, int):
                parts.append(f"{results} results")
            if parts:
                blocks.append(self._meta_text(*parts))
            blocks.append(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text", theme="one-dark", word_wrap=True,
                )
            )

        # ── web_fetch ──────────────────────────────────────────────────────────
        elif name == "web_fetch" and ok:
            meta   = metadata or {}
            parts  = []
            if isinstance(meta.get("status_code"), int):
                parts.append(str(meta["status_code"]))
            if isinstance(meta.get("content_length"), int):
                parts.append(f"{meta['content_length']} B")
            if isinstance(args.get("url"), str):
                parts.append(args["url"])
            if parts:
                blocks.append(self._meta_text(*parts))
            blocks.append(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text", theme="one-dark", word_wrap=True,
                )
            )

        # ── todos ──────────────────────────────────────────────────────────────
        elif name == "todos" and ok:
            blocks.append(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text", theme="one-dark", word_wrap=True,
                )
            )

        # ── memory ─────────────────────────────────────────────────────────────
        elif name == "memory" and ok:
            meta  = metadata or {}
            parts = []
            for k in ("action", "key"):
                v = args.get(k)
                if isinstance(v, str) and v:
                    parts.append(v)
            if isinstance(meta.get("found"), bool):
                parts.append("found" if meta["found"] else "missing")
            if parts:
                blocks.append(self._meta_text(*parts))
            blocks.append(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text", theme="one-dark", word_wrap=True,
                )
            )

        # ── fallback / error ───────────────────────────────────────────────────
        else:
            if error and not ok:
                blocks.append(
                    Panel(
                        Text(error, style="error"),
                        box=box.SIMPLE,
                        border_style="error",
                        padding=(0, 1),
                    )
                )
            display = truncate_text(output, self.config.model_name, self._max_block_tokens)
            if display.strip():
                blocks.append(
                    Syntax(display, "text", theme="one-dark", word_wrap=True)
                )

        if truncated:
            blocks.append(
                Text("  ⚠  output truncated", style="warning")
            )

        self.console.print()
        self.console.print(
            Panel(
                Group(*blocks),
                title=title,
                title_align="left",
                subtitle=Text(f" {'done' if ok else 'failed'} ", style=status_style),
                subtitle_align="right",
                border_style=border_style,
                box=_PANEL_BOX,
                padding=(0, 2),
            )
        )

    # ── MCP status ────────────────────────────────────────────────────────────

    def print_mcp_status(
        self,
        servers: list[dict[str, Any]],
        mcp_tool_names: list[str],
    ) -> None:
        if not servers:
            self.console.print(
                Text("  ◉  no MCP servers configured", style="muted")
            )
            return

        table = Table(
            box=_TABLE_BOX,
            border_style="border",
            show_header=True,
            header_style="muted",
            show_edge=False,
            padding=(0, 2),
        )
        table.add_column("Server",  style="bold #94a3b8", no_wrap=True)
        table.add_column("Status",  no_wrap=True)
        table.add_column("Tools",   justify="right", style="muted")

        _status_styles = {
            "connected":  ("connected",   "success"),
            "error":      ("error",       "error"),
            "connecting": ("connecting…", "warning"),
        }

        for server in servers:
            name   = str(server.get("name",   "unknown"))
            status = str(server.get("status", "unknown"))
            tools  = str(server.get("tools",  0))
            label, style = _status_styles.get(status, (status, "muted"))
            table.add_row(name, Text(label, style=style), tools)

        tools_line = (
            Text("  " + "  ·  ".join(mcp_tool_names), style="muted")
            if mcp_tool_names
            else Text("  no tools loaded", style="muted")
        )

        self.console.print()
        self.console.print(
            Panel(
                Group(table, Text(""), tools_line),
                title=Text(" ◉  MCP ", style="tool.mcp"),
                title_align="left",
                border_style="tool.mcp",
                box=_PANEL_BOX,
                padding=(0, 1),
            )
        )

    # ── Welcome screen ────────────────────────────────────────────────────────

    def print_welcome(self, title: str, version: str, cwd: str, model: str = "") -> None:
        PAT_ASCII = (
            " ██████╗  █████╗ ████████╗",
            " ██╔══██╗██╔══██╗╚══██╔══╝",
            " ██████╔╝███████║   ██║   ",
            " ██╔═══╝ ██╔══██║   ██║   ",
            " ██║     ██║  ██║   ██║   ",
            " ╚═╝     ╚═╝  ╚═╝   ╚═╝  ",
        )

        header = Text()
        header.append("  Welcome to\n", style="bold dim white")
        for line in PAT_ASCII:
            header.append(line + "\n", style="bold bright_green")
        header.append("\n")
        header.append("  v-" + version, style="bold green")
        header.append("   your intelligent coding partner\n", style="dim white")

        divider = Text("─" * 56, style="dim green")

        info = Text()
        info.append("  ● ", style="bold bright_green")
        info.append("model", style="dim white")
        info.append(" : ", style="dim green")
        info.append((model or self.config.model_name) + "\n", style="bold white")
        info.append("  ● ", style="bold bright_green")
        info.append("cwd  ", style="dim white")
        info.append(" : ", style="dim green")
        info.append(str(cwd) + "\n", style="white")

        hint = Text()
        hint.append("  type your message and press Enter  ", style="dim white")
        hint.append("·", style="dim green")
        hint.append("  Ctrl+C to interrupt", style="dim white")

        full = Group(
            Padding(header,  (1, 1, 0, 1)),
            Padding(divider, (0, 1)),
            Padding(info,    (0, 1)),
            Padding(hint,    (0, 1, 1, 1)),
        )

        self.console.print()
        self.console.print(
            Panel(
                full,
                border_style="green",
                box=box.HEAVY,
                padding=(0, 0),
                subtitle=Text(f" {title} ", style="bold bright_green"),
                subtitle_align="right",
            )
        )
        self.console.print()

    # ── Confirmation dialog ───────────────────────────────────────────────────

    def handle_confirmation(self, confirmation: ToolConfirmation) -> bool:
        blocks: list = []

        # Tool name + description row
        header = Text.assemble(
            (confirmation.tool_name, "bold tool"),
            ("   ", ""),
            (confirmation.description, "muted"),
        )
        blocks.append(header)

        # Optional shell command
        if confirmation.command:
            blocks.append(Text(""))
            blocks.append(
                Text.assemble(
                    ("  ❯  ", "muted"),
                    (confirmation.command, "tool.shell"),
                )
            )

        # Optional diff
        if confirmation.diff:
            blocks.append(Text(""))
            blocks.append(
                Syntax(
                    confirmation.diff.to_diff(),
                    "diff",
                    theme="one-dark",
                    word_wrap=True,
                )
            )

        self.console.print()
        self.console.print(
            Panel(
                Group(*blocks),
                title=Text(" ⚠  approval required ", style="bold warning"),
                title_align="left",
                subtitle=Text(" [y] approve   [n] deny ", style="muted"),
                subtitle_align="right",
                border_style="warning",
                box=_PANEL_BOX,
                padding=(1, 2),
            )
        )

        response = Prompt.ask(
            Text.assemble(("  approve?", "bold warning"), (" [y/n]", "muted")),
            choices=["y", "n", "yes", "no"],
            default="n",
            show_choices=False,
        )
        self.console.print()
        return response.lower() in {"y", "yes"}