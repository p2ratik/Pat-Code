from pathlib import Path
from typing import Any
import re
import shutil

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from config.config import Config
from tools.base import ToolConfirmation
from utils.paths import display_path_rel_to_cwd
from utils.text import truncate_text


AGENT_THEME = Theme(
    {
        "info": "#7dd3fc",
        "warning": "#f59e0b",
        "error": "#ef4444 bold",
        "success": "#34d399 bold",
        "muted": "#7b8495",
        "dim": "dim",
        "border": "#334155",
        "border.active": "#38bdf8",
        "surface": "#e5e7eb",
        "surface.soft": "#cbd5e1",
        "accent": "#2dd4bf",
        "accent.blue": "#60a5fa",
        "user": "#93c5fd bold",
        "assistant": "#f8fafc",
        "tool": "#cbd5e1 bold",
        "tool.read": "#94a3b8",
        "tool.write": "#2dd4bf bold",
        "tool.shell": "#a78bfa bold",
        "tool.network": "#38bdf8 bold",
        "tool.memory": "#34d399",
        "tool.mcp": "#22d3ee",
        "code": "#dbeafe",
    }
)

_console: Console | None = None

_QUIET_SUCCESS_TOOLS = {
    "read_file",
    "list_dir",
    "grep",
    "glob",
    "search_entity",
    "traverse_graph",
    "retrieve_entity",
}

_VISIBLE_EDIT_TOOLS = {
    "write_file",
    "edit",
    "apply_patch",
    "patch",
    "create_file",
}


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(
            theme=AGENT_THEME,
            highlight=False,
            soft_wrap=False,
            legacy_windows=False,
        )
    return _console


def _tool_border(tool_kind: str | None, name: str) -> str:
    if name in _VISIBLE_EDIT_TOOLS:
        return "tool.write"
    if tool_kind:
        return f"tool.{tool_kind}"
    return "tool"


def _short_path(path: str | None, cwd: str | Path | None) -> str:
    if not path:
        return ""
    if cwd:
        return str(display_path_rel_to_cwd(path, cwd))
    return str(path)


class TUI:
    def __init__(self, _console: Console, config: Config):
        self.console = _console
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self._max_block_tokens = 2500
        self.cwd = config.cwd
        self.config = config
        self._stream_buffer: list[str] = []

    def _sync_console_size(self) -> None:
        size = shutil.get_terminal_size(
            fallback=(max(40, self.console.size.width), max(10, self.console.size.height))
        )
        self.console._width = max(40, size.columns)
        self.console._height = max(10, size.lines)

    def _panel_width(self) -> int | None:
        self._sync_console_size()
        return None

    def _rule(self, label: str = "", style: str = "border") -> Rule:
        title = Text(f" {label} ", style="muted") if label else ""
        return Rule(title, style=style, align="left")

    def begin_assistant(self) -> None:
        self._sync_console_size()
        self._stream_buffer = []
        self.console.print()
        self.console.print(self._rule("assistant", "border.active"))

    def stream_assistant_delta(self, content: str) -> None:
        self._stream_buffer.append(content)

    def end_assistant(self) -> None:
        full_text = "".join(self._stream_buffer).strip()
        self._stream_buffer = []
        if full_text:
            body = Markdown(full_text, code_theme="github-dark", hyperlinks=True)
            self.console.print(
                Panel(
                    Padding(body, (0, 1)),
                    border_style="border",
                    box=box.ROUNDED,
                    padding=(1, 2),
                    width=self._panel_width(),
                )
            )
        self.console.print()

    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[tuple[str, Any]]:
        preferred_order = {
            "read_file": ["path", "offset", "limit"],
            "write_file": ["path", "create_directories", "content"],
            "edit": ["path", "replace_all", "old_string", "new_string"],
            "apply_patch": ["path", "patch"],
            "shell": ["command", "timeout", "cwd"],
            "list_dir": ["path", "include_hidden"],
            "grep": ["path", "case_insensitive", "pattern"],
            "glob": ["path", "pattern"],
            "todos": ["id", "action", "content"],
            "memory": ["action", "key", "value"],
            "search_entity": ["keyword", "top_k"],
            "traverse_graph": [
                "start_ids",
                "direction",
                "hops",
                "edge_types",
                "node_types",
            ],
            "retrieve_entity": ["entity_id"],
        }
        ordered: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for key in preferred_order.get(tool_name, []):
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
        ordered.extend((key, value) for key, value in args.items() if key not in seen)
        return ordered

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="muted", justify="right", no_wrap=True, min_width=10)
        table.add_column(style="code", overflow="fold")

        for key, value in self._ordered_args(tool_name, args):
            if isinstance(value, str) and key in {
                "content",
                "old_string",
                "new_string",
                "patch",
            }:
                line_count = len(value.splitlines()) or 0
                byte_count = len(value.encode("utf-8", errors="replace"))
                value = f"<{line_count} lines, {byte_count} bytes>"
            elif not isinstance(value, str):
                value = str(value)
            table.add_row(key, value)
        return table

    def _tool_title(self, name: str, call_id: str, status: str, success: bool | None) -> Text:
        if success is None:
            state = Text("running", style="warning")
        elif success:
            state = Text("done", style="success")
        else:
            state = Text("failed", style="error")

        title = Text()
        title.append("tool ", style="muted")
        title.append(name, style="tool")
        title.append("  ")
        title.append(f"#{call_id[:8]}", style="muted")
        title.append("  ")
        title.append_text(state)
        if status:
            title.append(f"  {status}", style="muted")
        return title

    def _display_args(self, arguments: dict[str, Any]) -> dict[str, Any]:
        display_args = dict(arguments)
        for key in ("path", "cwd"):
            val = display_args.get(key)
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(display_path_rel_to_cwd(val, self.cwd))
        return display_args

    def tool_call_start(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        arguments: dict[str, Any],
    ) -> None:
        self._sync_console_size()
        self._tool_args_by_call_id[call_id] = arguments
        if name in _QUIET_SUCCESS_TOOLS:
            summary = self._metadata_line(name, arguments, {}, None)
            suffix = f"  {summary}" if summary else ""
            self.console.print(
                Text.assemble(
                    ("  tool ", "muted"),
                    (name, "tool"),
                    ("  ", "muted"),
                    (f"#{call_id[:8]}", "muted"),
                    ("  running", "warning"),
                    (suffix, "muted"),
                )
            )
            return

        display_args = self._display_args(arguments)
        body = (
            self._render_args_table(name, display_args)
            if display_args
            else Text("no arguments", style="muted")
        )
        self.console.print()
        self.console.print(
            Panel(
                body,
                title=self._tool_title(name, call_id, "", None),
                title_align="left",
                border_style=_tool_border(tool_kind, name),
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._panel_width(),
            )
        )

    def _extract_read_file_code(self, text: str) -> tuple[int, str] | None:
        body = text
        header_match = re.match(r"^Showing lines (\d+)-(\d+) of (\d+)\n\n", text)
        if header_match:
            body = text[header_match.end() :]

        code_lines: list[str] = []
        start_line: int | None = None
        for line in body.splitlines():
            match = re.match(r"^\s*(\d+)\|(.*)$", line)
            if not match:
                return None
            line_no = int(match.group(1))
            if start_line is None:
                start_line = line_no
            code_lines.append(match.group(2))

        if start_line is None:
            return None
        return start_line, "\n".join(code_lines)

    def _guess_language(self, path: str | None) -> str:
        if not path:
            return "text"
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".json": "json",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".kt": "kotlin",
            ".swift": "swift",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".css": "css",
            ".html": "html",
            ".xml": "xml",
            ".sql": "sql",
        }.get(Path(path).suffix.lower(), "text")

    def _metadata_line(
        self,
        name: str,
        args: dict[str, Any],
        metadata: dict[str, Any],
        exit_code: int | None,
    ) -> str:
        parts: list[str] = []
        path = metadata.get("path") or args.get("path") or args.get("cwd")
        if isinstance(path, str):
            parts.append(_short_path(path, self.cwd))
        if name == "shell" and exit_code is not None:
            parts.append(f"exit {exit_code}")
        if isinstance(metadata.get("entries"), int):
            parts.append(f"{metadata['entries']} entries")
        if isinstance(metadata.get("matches"), int):
            parts.append(f"{metadata['matches']} matches")
        if isinstance(metadata.get("results"), int):
            parts.append(f"{metadata['results']} results")
        if isinstance(metadata.get("content_length"), int):
            parts.append(f"{metadata['content_length']} bytes")
        return " | ".join(parts)

    def _build_tool_blocks(
        self,
        call_id: str,
        name: str,
        success: bool,
        output: str,
        error: str | None,
        metadata: dict[str, Any],
        diff: str | None,
        exit_code: int | None,
    ) -> list[Any]:
        blocks: list[Any] = []

        if error and not success:
            blocks.append(Text(error, style="error"))

        if name in {"write_file", "edit", "apply_patch", "patch"} and diff:
            output_line = output.strip() if output.strip() else "Completed"
            blocks.append(Text(output_line, style="muted"))
            blocks.append(
                Syntax(
                    truncate_text(diff, self.config.model_name, self._max_block_tokens),
                    "diff",
                    theme="github-dark",
                    word_wrap=True,
                )
            )
            return blocks

        if name == "shell":
            command = self._tool_args_by_call_id.get(call_id, {}).get("command")
            if isinstance(command, str) and command.strip():
                blocks.append(Text(f"$ {command.strip()}", style="muted"))

        if name == "read_file" and success:
            primary_path = metadata.get("path")
            extracted = self._extract_read_file_code(output)
            if isinstance(primary_path, str) and extracted:
                start_line, code = extracted
                shown_start = metadata.get("shown_start")
                shown_end = metadata.get("shown_end")
                total_lines = metadata.get("total_lines")
                header = _short_path(primary_path, self.cwd)
                if shown_start and shown_end and total_lines:
                    header = f"{header} | lines {shown_start}-{shown_end} of {total_lines}"
                blocks.append(Text(header, style="muted"))
                blocks.append(
                    Syntax(
                        code,
                        self._guess_language(primary_path),
                        theme="github-dark",
                        line_numbers=True,
                        start_line=start_line,
                        word_wrap=False,
                    )
                )
                return blocks

        output_display = truncate_text(
            output,
            self.config.model_name,
            self._max_block_tokens,
        )
        if output_display.strip():
            blocks.append(
                Syntax(output_display, "text", theme="github-dark", word_wrap=True)
            )
        elif not blocks:
            blocks.append(Text("completed without output", style="muted"))
        return blocks

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
        self._sync_console_size()
        metadata = dict(metadata or {})
        metadata["call_id"] = call_id

        if name in _QUIET_SUCCESS_TOOLS and success:
            args = self._tool_args_by_call_id.get(call_id, {})
            status = self._metadata_line(name, args, metadata, exit_code)
            suffix = f"  {status}" if status else ""
            self.console.print(
                Text.assemble(
                    ("  tool ", "muted"),
                    (name, "tool"),
                    ("  ", "muted"),
                    (f"#{call_id[:8]}", "muted"),
                    ("  done", "success"),
                    (suffix, "muted"),
                )
            )
            return

        args = self._tool_args_by_call_id.get(call_id, {})
        status = self._metadata_line(name, args, metadata, exit_code)
        blocks = self._build_tool_blocks(
            call_id, name, success, output, error, metadata, diff, exit_code
        )
        if truncated:
            blocks.append(Text("output truncated", style="warning"))

        self.console.print()
        self.console.print(
            Panel(
                Group(*blocks),
                title=self._tool_title(name, call_id, status, success),
                title_align="left",
                border_style=_tool_border(tool_kind, name) if success else "error",
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._panel_width(),
            )
        )

    def print_mcp_status(
        self,
        servers: list[dict[str, Any]],
        mcp_tool_names: list[str],
    ) -> None:
        self._sync_console_size()
        table = Table(
            box=box.SIMPLE,
            border_style="border",
            show_header=True,
            header_style="muted",
            show_edge=False,
            padding=(0, 2),
        )
        table.add_column("Server", style="surface.soft", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Tools", justify="right", style="muted")

        if servers:
            for server in servers:
                status = str(server.get("status", "unknown"))
                style = {
                    "connected": "success",
                    "error": "error",
                    "connecting": "warning",
                }.get(status, "muted")
                table.add_row(
                    str(server.get("name", "unknown")),
                    Text(status, style=style),
                    str(server.get("tools", 0)),
                )
        else:
            table.add_row("none", Text("not configured", style="muted"), "0")

        tool_summary = (
            ", ".join(mcp_tool_names[:8]) + (" ..." if len(mcp_tool_names) > 8 else "")
            if mcp_tool_names
            else "no MCP tools loaded"
        )

        self.console.print(
            Panel(
                Group(table, Text(tool_summary, style="muted")),
                title=Text("mcp", style="accent.blue"),
                title_align="left",
                border_style="border",
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._panel_width(),
            )
        )

    def print_welcome(self, title: str, version: str, cwd: str, model: str = "") -> None:
        self._sync_console_size()
        width = self._panel_width()
        model_name = model or self.config.model_name

        header = Text()
        header.append(f"{title} ", style="accent bold")
        header.append(f"v{version}", style="muted")
        header.append("  |  ", style="border")
        header.append("coding agent", style="surface.soft")

        meta = Table.grid(padding=(0, 2))
        meta.add_column(style="muted", no_wrap=True)
        meta.add_column(style="surface")
        meta.add_row("model", model_name)
        meta.add_row("cwd", str(cwd))

        hint = Text("Type a message and press Enter. Ctrl+C interrupts.", style="muted")
        body = Group(
            Align.left(header),
            Text(""),
            meta,
            Text(""),
            hint,
        )

        self.console.clear()
        self.console.print(
            Panel(
                body,
                border_style="border.active",
                box=box.ROUNDED,
                padding=(1, 2),
                width=width,
            )
        )

    def handle_confirmation(self, confirmation: ToolConfirmation) -> bool:
        self._sync_console_size()
        blocks: list[Any] = [
            Text(confirmation.tool_name, style="tool.write"),
            Text(confirmation.description, style="surface.soft"),
        ]

        if confirmation.command:
            blocks.append(Text(""))
            blocks.append(Text(f"$ {confirmation.command}", style="warning"))

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
                title=Text("approval required", style="warning"),
                title_align="left",
                subtitle=Text("y approve | n deny", style="muted"),
                subtitle_align="right",
                border_style="warning",
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._panel_width(),
            )
        )

        response = Prompt.ask(
            Text.assemble(("approve?", "warning"), (" [y/n]", "muted")),
            choices=["y", "n", "yes", "no"],
            default="n",
            show_choices=False,
        )
        self.console.print()
        return response.lower() in {"y", "yes"}

    def show_help(self) -> None:
        self._sync_console_size()
        rows = [
            ("/help", "Show this help"),
            ("/clear", "Clear conversation context"),
            ("/config", "Show current configuration"),
            ("/model <name>", "Change model name"),
            ("/approval <policy>", "Set approval policy"),
            ("/tools", "List available tools"),
            ("/mcp", "Show MCP server status"),
            ("/stats", "Show session statistics"),
            ("/save", "Save current session"),
            ("/sessions", "List saved sessions"),
            ("/resume <session_id>", "Resume a saved session"),
            ("/checkpoint", "Create a checkpoint"),
            ("/restore <checkpoint_id>", "Restore from checkpoint"),
            ("/exit", "Exit the CLI"),
        ]

        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_column(style="accent", no_wrap=True)
        table.add_column(style="surface.soft")
        for command, description in rows:
            table.add_row(command, description)

        self.console.print()
        self.console.print(
            Panel(
                table,
                title=Text("commands", style="accent"),
                title_align="left",
                border_style="border",
                box=box.ROUNDED,
                padding=(1, 2),
                width=self._panel_width(),
            )
        )
