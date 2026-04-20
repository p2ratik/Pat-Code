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
# Palette anchored to the green welcome screen — deep teal/emerald accents,
# warm amber for "in-flight" state, and vivid green check for success.
from rich.theme import Theme

AGENT_THEME = Theme({
    # Core semantics (muted, professional)
    "info":      "#60a5fa",     # soft blue
    "warning":   "#d97706",     # muted amber
    "error":     "#b91c1c",     # deep red
    "success":   "#059669",     # deep green
    "muted":     "#6b7280",     # gray
    "dim":       "dim",
    "border":    "#374151",     # neutral border

    # Roles
    "user":      "#2563eb",
    "assistant": "#e5e7eb",

    # Tool states (ONLY place where color matters)
    "tool.running": "#6b7280",
    "tool.done":    "#059669",
    "tool.failed":  "#b91c1c",

    # Tool types → neutral (important change)
    "tool":         "#9ca3af",
    "tool.read":    "#9ca3af",
    "tool.write":   "#9ca3af",
    "tool.shell":   "#9ca3af",
    "tool.network": "#9ca3af",
    "tool.memory":  "#9ca3af",
    "tool.mcp":     "#9ca3af",

    # Code stays colorful (your requirement)
    "code": "#d1d5db",

    # Accent (used sparingly)
    "accent": "#2563eb",
})

# Box styles
_PANEL_BOX = box.ROUNDED
_TABLE_BOX = box.SIMPLE_HEAD

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
        # Buffer for streaming assistant text → rendered as Markdown at end
        self._stream_buffer: list[str] = []

    # ── Streaming ─────────────────────────────────────────────────────────────

    def stream_assistant_delta(self, content: str) -> None:
        """Buffer streamed deltas; we render as Markdown after stream ends."""
        self._stream_buffer.append(content)

    def begin_assistant(self) -> None:
        self._stream_buffer = []
        self.console.print()
        self.console.print(
            Rule(
                Text("  assistant  ", style="bold"),
                style="border",
                align="left",
            )
        )   
        self.console.print()

    def end_assistant(self) -> None:
        """Flush buffer as rendered Markdown then close the rule."""
        full_text = "".join(self._stream_buffer).strip()
        self._stream_buffer = []

        if full_text:
            md = Markdown(
                full_text,
                code_theme="github-dark",
                hyperlinks=True,
            )
            self.console.print(
                Panel(
                    Padding(md, (0, 1)),
                    border_style="border",
                    padding=(1, 2),
                )
            )

        self.console.print()
        self.console.print(Rule(style="#1a2e1e"))

    def show_help(self) -> None:
        help_lines = [
            "/help — Show this help",
            "/clear — Clear conversation context",
            "/config — Show current configuration",
            "/model <name> — Change model name",
            "/approval <policy> — Set approval policy",
            "/tools — List available tools",
            "/mcp — Show MCP server status",
            "/stats — Show session statistics",
            "/save — Save current session",
            "/sessions — List saved sessions",
            "/resume <session_id> — Resume a saved session",
            "/checkpoint — Create a checkpoint",
            "/restore <checkpoint_id> — Restore from checkpoint",
            "/exit or /quit — Exit the CLI",
        ]

        rows = []
        for line in help_lines:
            cmd, _, desc = line.partition(" — ")
            rows.append((cmd.strip(), desc.strip()))

        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_column(style="bold #22d3ee", no_wrap=True)
        table.add_column(style="assistant")
        for cmd, desc in rows:
            table.add_row(cmd, desc)

        self.console.print()
        self.console.print(
            Panel(
                table,
                title=Text(" ⌘  Commands ", style="bold #10b981"),
                title_align="left",
                border_style="#1e3a2a",
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

        icon = _tool_icon(tool_kind)

        title = Text.assemble(
            (f"{icon} ", "muted"),
            (name, "bold"),
            ("   ", ""),
            (f"#{call_id[:6]}", "muted"),
        )

        subtitle = Text("running", style="muted")

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
                subtitle=subtitle,
                border_style="border",   # ✅ always neutral
                padding=(1, 2),
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
        """Render a dimmed metadata line like  path · lines 1-40 of 200"""
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
        status_style = "success" if success else "error"
        status_icon = "✓" if success else "✗"

        title = Text.assemble(
            (f"{status_icon} ", status_style),
            (name, "bold"),
            ("   ", ""),
            (f"#{call_id[:6]}", "muted"),
        )

        args = self._tool_args_by_call_id.get(call_id, {})

        primary_path = None
        blocks = []
        if isinstance(metadata, dict) and isinstance(metadata.get("path"), str):
            primary_path = metadata.get("path")

        if name == "read_file" and success:
            if primary_path:
                start_line, code = self._extract_read_file_code(output)

                shown_start = metadata.get("shown_start")
                shown_end = metadata.get("shown_end")
                total_lines = metadata.get("total_lines")
                pl = self._guess_language(primary_path)

                header_parts = [display_path_rel_to_cwd(primary_path, self.cwd)]
                header_parts.append(" • ")

                if shown_start and shown_end and total_lines:
                    header_parts.append(
                        f"lines {shown_start}-{shown_end} of {total_lines}"
                    )

                header = "".join(header_parts)
                blocks.append(Text(header, style="muted"))
                blocks.append(
                    Syntax(
                        code,
                        pl,
                        theme="github-dark",
                        line_numbers=True,
                        start_line=start_line,
                        word_wrap=False,
                    )
                )
            else:
                output_display = truncate_text(
                    output,
                    "",
                    self._max_block_tokens,
                )
                blocks.append(
                    Syntax(
                        output_display,
                        "text",
                        theme="github-dark",
                        word_wrap=False,
                    )
                )
        elif name in {"write_file", "edit"} and success and diff:
            output_line = output.strip() if output.strip() else "Completed"
            blocks.append(Text(output_line, style="muted"))
            diff_text = diff
            diff_display = truncate_text(
                diff_text,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    diff_display,
                    "diff",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "shell" and success:
            command = args.get("command")
            if isinstance(command, str) and command.strip():
                blocks.append(Text(f"$ {command.strip()}", style="muted"))

            if exit_code is not None:
                blocks.append(Text(f"exit_code={exit_code}", style="muted"))

            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "list_dir" and success:
            entries = metadata.get("entries")
            path = metadata.get("path")
            summary = []
            if isinstance(path, str):
                summary.append(path)

            if isinstance(entries, int):
                summary.append(f"{entries} entries")

            if summary:
                blocks.append(Text(" • ".join(summary), style="muted"))

            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "grep" and success:
            matches = metadata.get("matches")
            files_searched = metadata.get("files_searched")
            summary = []
            if isinstance(matches, int):
                summary.append(f"{matches} matches")
            if isinstance(files_searched, int):
                summary.append(f"searched {files_searched} files")

            if summary:
                blocks.append(Text(" • ".join(summary), style="muted"))

            output_display = truncate_text(
                output, self.config.model_name, self._max_block_tokens
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "glob" and success:
            matches = metadata.get("matches")
            if isinstance(matches, int):
                blocks.append(Text(f"{matches} matches", style="muted"))

            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "web_search" and success:
            results = metadata.get("results")
            query = args.get("query")
            summary = []
            if isinstance(query, str):
                summary.append(query)
            if isinstance(results, int):
                summary.append(f"{results} results")

            if summary:
                blocks.append(Text(" • ".join(summary), style="muted"))

            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "web_fetch" and success:
            status_code = metadata.get("status_code")
            content_length = metadata.get("content_length")
            url = args.get("url")
            summary = []
            if isinstance(status_code, int):
                summary.append(str(status_code))
            if isinstance(content_length, int):
                summary.append(f"{content_length} bytes")
            if isinstance(url, str):
                summary.append(url)

            if summary:
                blocks.append(Text(" • ".join(summary), style="muted"))

            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "todos" and success:
            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        elif name == "memory" and success:
            action = args.get("action")
            key = args.get("key")
            found = metadata.get("found")
            summary = []
            if isinstance(action, str) and action:
                summary.append(action)
            if isinstance(key, str) and key:
                summary.append(key)
            if isinstance(found, bool):
                summary.append("found" if found else "missing")

            if summary:
                blocks.append(Text(" • ".join(summary), style="muted"))
            output_display = truncate_text(
                output,
                self.config.model_name,
                self._max_block_tokens,
            )
            blocks.append(
                Syntax(
                    output_display,
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
        else:
            if error and not success:
                blocks.append(Text(error, style="error"))

            output_display = truncate_text(
                output, self.config.model_name, self._max_block_tokens
            )
            if output_display.strip():
                blocks.append(
                    Syntax(
                        output_display,
                        "text",
                        theme="github-dark",
                        word_wrap=True,
                    )
                )
            else:
                blocks.append(Text("(no output)", style="muted"))

        if truncated:
            blocks.append(Text("note: tool output was truncated", style="warning"))

        subtitle = Text(
            "completed" if success else "failed",
            style=status_style
        )

        panel = Panel(
            Group(*blocks),
            title=title,
            subtitle=subtitle,
            border_style="border",   
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)

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
        table.add_column("Server",  style="bold #22d3ee", no_wrap=True)
        table.add_column("Status",  no_wrap=True)
        table.add_column("Tools",   justify="right", style="muted")

        _status_styles = {
            "connected":  ("connected",   "bold #22c55e"),
            "error":      ("error",       "bold #ef4444"),
            "connecting": ("connecting…", "bold #f59e0b"),
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
                title=Text(" ◉  MCP ", style="bold #22d3ee"),
                title_align="left",
                border_style="#164e63",          # cyan-900
                box=_PANEL_BOX,
                padding=(0, 1),
            )
        )

    # ── Welcome screen ────────────────────────────────────────────────────────
    # (unchanged — user explicitly asked to keep it)

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

        header = Text.assemble(
            (confirmation.tool_name, "bold #22d3ee"),
            ("   ", ""),
            (confirmation.description, "muted"),
        )
        blocks.append(header)

        if confirmation.command:
            blocks.append(Text(""))
            blocks.append(
                Text.assemble(
                    ("  ❯  ", "muted"),
                    (confirmation.command, "bold #c084fc"),
                )
            )

        if confirmation.diff:
            blocks.append(Text(""))
            blocks.append(
                Syntax(
                    confirmation.diff.to_diff(),
                    "diff",
                    theme="github-dark",
                    word_wrap=True,
                )
            )

        self.console.print()
        self.console.print(
            Panel(
                Group(*blocks),
                title=Text(" ⚠  approval required ", style="bold #fbbf24"),
                title_align="left",
                subtitle=Text(" [y] approve   [n] deny ", style="muted"),
                subtitle_align="right",
                border_style="#78350f",          # amber-900
                box=_PANEL_BOX,
                padding=(1, 2),
            )
        )

        response = Prompt.ask(
            Text.assemble(("  approve?", "bold #fbbf24"), (" [y/n]", "muted")),
            choices=["y", "n", "yes", "no"],
            default="n",
            show_choices=False,
        )
        self.console.print()
        return response.lower() in {"y", "yes"}