from __future__ import annotations

from typing import Any

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel
from rich.console import Group

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, LoadingIndicator, ProgressBar, RichLog, Static

from config.config import ApprovalPolicy
from tools.base import ToolConfirmation
from utils.paths import display_path_rel_to_cwd
from utils.text import truncate_text


QUIET_OUTPUT_TOOLS = {
    "read_file",
    "list_dir",
    "grep",
    "glob",
    "search_entity",
    "traverse_graph",
    "retrieve_entity",
}

EDIT_TOOLS = {"write_file", "edit", "apply_patch", "patch", "create_file"}


class ToolRow(Static):
    DEFAULT_CSS = """
    ToolRow {
        height: auto;
        min-height: 1;
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text-muted;
    }

    ToolRow.running {
        color: $warning;
    }

    ToolRow.success {
        color: $success;
    }

    ToolRow.failed {
        color: $error;
    }
    """

    def __init__(self, call_id: str, name: str, summary: str) -> None:
        super().__init__()
        self.call_id = call_id
        self.name = name
        self.summary = summary
        self._tick = 0
        self._timer = None

    def on_mount(self) -> None:
        self.add_class("running")
        self._timer = self.set_interval(0.18, self._animate)
        self._render("running")

    def _animate(self) -> None:
        self._tick = (self._tick + 1) % 10
        bar = "#" * (self._tick + 1)
        bar = f"{bar:<10}"
        self.update(f"  {self.name}  #{self.call_id[:8]}  running  [{bar}]  {self.summary}")

    def _render(self, state: str) -> None:
        self.update(f"  {self.name}  #{self.call_id[:8]}  {state}  {self.summary}")

    def complete(self, success: bool, summary: str = "") -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.remove_class("running")
        self.add_class("success" if success else "failed")
        self.summary = summary or self.summary
        self._render("done" if success else "failed")


class TextualTUI:
    def __init__(self, app: "PatTextualApp") -> None:
        self.app = app
        self._assistant_buffer: list[str] = []
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self._tool_rows: dict[str, ToolRow] = {}
        self._max_block_tokens = 2500

    @property
    def cwd(self):
        return self.app.cli.config.cwd

    @property
    def config(self):
        return self.app.cli.config

    def print_welcome(self, title: str, version: str, cwd: str, model: str = "") -> None:
        self.app.set_meta(title, version, model or self.config.model_name, str(cwd))
        self.app.write_info("Welcome to PAT. Type your message and press Enter.")

    def print_mcp_status(self, servers: list[dict[str, Any]], mcp_tool_names: list[str]) -> None:
        connected = sum(1 for server in servers if server.get("status") == "connected")
        self.app.set_mcp_status(connected, len(servers), len(mcp_tool_names))

    def begin_assistant(self) -> None:
        self._assistant_buffer = []
        self.app.set_busy("Assistant is responding")

    def stream_assistant_delta(self, content: str) -> None:
        self._assistant_buffer.append(content)

    def end_assistant(self) -> None:
        content = "".join(self._assistant_buffer).strip()
        self._assistant_buffer = []
        if content:
            self.app.write_assistant(content)
        self.app.clear_busy()

    def _short_path(self, path: str | None) -> str:
        if not path:
            return ""
        return str(display_path_rel_to_cwd(path, self.cwd))

    def _summary(self, name: str, args: dict[str, Any], metadata: dict[str, Any] | None = None) -> str:
        metadata = metadata or {}
        parts: list[str] = []
        path = metadata.get("path") or args.get("path") or args.get("cwd")
        if isinstance(path, str):
            parts.append(self._short_path(path))
        if isinstance(args.get("pattern"), str):
            parts.append(f"pattern: {args['pattern']}")
        if isinstance(args.get("command"), str):
            parts.append(args["command"])
        if isinstance(metadata.get("entries"), int):
            parts.append(f"{metadata['entries']} entries")
        if isinstance(metadata.get("matches"), int):
            parts.append(f"{metadata['matches']} matches")
        if isinstance(metadata.get("results"), int):
            parts.append(f"{metadata['results']} results")
        return " | ".join(parts)

    def tool_call_start(
        self,
        call_id: str,
        name: str,
        tool_kind: str | None,
        arguments: dict[str, Any],
    ) -> None:
        self._tool_args_by_call_id[call_id] = arguments
        row = ToolRow(call_id, name, self._summary(name, arguments))
        self._tool_rows[call_id] = row
        self.app.add_tool_row(row)
        self.app.set_busy(f"Running {name}")

    def _render_diff_panel(self, name: str, output: str, diff: str) -> Panel:
        output_line = output.strip() if output.strip() else "Completed"
        return Panel(
            Group(
                Text(output_line, style="dim"),
                Syntax(
                    truncate_text(diff, self.config.model_name, self._max_block_tokens),
                    "diff",
                    theme="github-dark",
                    word_wrap=True,
                ),
            ),
            title=f"{name} changes",
            border_style="cyan",
        )

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
        args = self._tool_args_by_call_id.get(call_id, {})
        summary = self._summary(name, args, metadata)
        row = self._tool_rows.get(call_id)
        if row:
            row.complete(success, summary)

        if not success:
            self.app.write_error(error or output or f"{name} failed")
        elif name in EDIT_TOOLS and diff:
            self.app.write_renderable(self._render_diff_panel(name, output, diff))
        elif name not in QUIET_OUTPUT_TOOLS and output.strip():
            self.app.write_renderable(
                Syntax(
                    truncate_text(output, self.config.model_name, self._max_block_tokens),
                    "text",
                    theme="github-dark",
                    word_wrap=True,
                )
            )

        if truncated:
            self.app.write_info("Tool output was truncated.")
        self.app.clear_busy()

    def handle_confirmation(self, confirmation: ToolConfirmation) -> bool:
        return True

    def show_help(self) -> None:
        self.app.write_assistant(
            "\n".join(
                [
                    "## Commands",
                    "- `/help` - Show commands",
                    "- `/clear` - Clear conversation history",
                    "- `/config` - Show current configuration",
                    "- `/model <name>` - Change the model",
                    "- `/approval <mode>` - Change approval mode",
                    "- `/stats` - Show session statistics",
                    "- `/tools` - List available tools",
                    "- `/mcp` - Show MCP server status",
                    "- `/exit` or `/quit` - Exit the agent",
                ]
            )
        )


class PatTextualApp(App[None]):
    CSS = """
    Screen {
        background: #0b1017;
        color: #dbeafe;
    }

    #root {
        height: 100%;
        width: 100%;
    }

    #sidebar {
        width: 28;
        min-width: 22;
        max-width: 34;
        padding: 1;
        background: #101820;
        border-right: solid #263446;
    }

    #brand {
        color: #2dd4bf;
        text-style: bold;
        margin-bottom: 1;
    }

    .side-label {
        color: #7b8495;
        margin-top: 1;
    }

    .side-value {
        color: #e5e7eb;
    }

    #main {
        width: 1fr;
        height: 100%;
    }

    #transcript {
        height: 1fr;
        padding: 1 2;
        background: #0b1017;
        border-bottom: solid #263446;
    }

    #tool-strip {
        height: auto;
        max-height: 9;
        padding: 0 1;
        background: #0d141c;
        border-bottom: solid #263446;
    }

    #status-row {
        height: 2;
        padding: 0 1;
        background: #101820;
        color: #7b8495;
    }

    #input {
        height: 3;
        border: tall #334155;
        background: #0b1017;
        color: #f8fafc;
    }

    #input:focus {
        border: tall #38bdf8;
    }

    ProgressBar {
        width: 24;
        margin: 0 1;
    }

    LoadingIndicator {
        width: 4;
    }
    """

    BINDINGS = [
        ("ctrl+c", "interrupt", "Interrupt"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, cli: Any) -> None:
        super().__init__()
        self.cli = cli
        self.tui = TextualTUI(self)
        self._busy_count = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="root"):
            with Vertical(id="sidebar"):
                yield Label("PAT", id="brand")
                yield Label("model", classes="side-label")
                yield Label("", id="model", classes="side-value")
                yield Label("project", classes="side-label")
                yield Label("", id="cwd", classes="side-value")
                yield Label("mcp", classes="side-label")
                yield Label("not loaded", id="mcp", classes="side-value")
            with Vertical(id="main"):
                yield RichLog(id="transcript", wrap=True, highlight=True, markup=True)
                yield Container(id="tool-strip")
                with Horizontal(id="status-row"):
                    yield LoadingIndicator(id="spinner")
                    yield ProgressBar(id="progress", total=100, show_eta=False)
                    yield Label("idle", id="status")
                yield Input(placeholder="Type your message and press Enter", id="input")
        yield Header(show_clock=True)
        yield Footer()

    async def on_mount(self) -> None:
        self.cli.tui = self.tui
        self.query_one("#spinner", LoadingIndicator).display = False
        self.query_one("#progress", ProgressBar).display = False
        from agent.agent import Agent

        self.agent_context = Agent(self.cli.config)
        self.cli.agent = await self.agent_context.__aenter__()
        self.tui.print_welcome(
            title="PAT",
            version="2.0.1",
            cwd=self.cli.config.cwd,
            model=self.cli.config.model_name,
        )
        self.cli._print_mcp_snapshot()
        self.query_one("#input", Input).focus()

    async def on_unmount(self) -> None:
        if getattr(self, "agent_context", None):
            await self.agent_context.__aexit__(None, None, None)

    def set_meta(self, title: str, version: str, model: str, cwd: str) -> None:
        self.query_one("#brand", Label).update(f"{title} v{version}")
        self.query_one("#model", Label).update(model)
        self.query_one("#cwd", Label).update(cwd)

    def set_mcp_status(self, connected: int, total: int, tools: int) -> None:
        self.query_one("#mcp", Label).update(f"{connected}/{total} servers | {tools} tools")

    def set_busy(self, message: str) -> None:
        self._busy_count += 1
        self.query_one("#spinner", LoadingIndicator).display = True
        progress = self.query_one("#progress", ProgressBar)
        progress.display = True
        progress.update(progress=min(95, 15 + (self._busy_count * 17) % 80))
        self.query_one("#status", Label).update(message)

    def clear_busy(self) -> None:
        self.query_one("#spinner", LoadingIndicator).display = False
        progress = self.query_one("#progress", ProgressBar)
        progress.update(progress=100)
        progress.display = False
        self.query_one("#status", Label).update("idle")

    def write_renderable(self, renderable: Any) -> None:
        self.query_one("#transcript", RichLog).write(renderable)

    def write_info(self, message: str) -> None:
        self.write_renderable(Text(message, style="dim"))

    def write_error(self, message: str) -> None:
        self.write_renderable(Text(message, style="bold red"))

    def write_assistant(self, content: str) -> None:
        self.write_renderable(Markdown(content, code_theme="github-dark"))

    def add_tool_row(self, row: ToolRow) -> None:
        strip = self.query_one("#tool-strip", Container)
        strip.mount(row)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        event.input.value = ""
        if not message:
            return
        if message in {"/exit", "/quit"}:
            self.exit()
            return
        self.query_one("#transcript", RichLog).write(Text(f"USER: {message}", style="bold cyan"))
        self.run_agent(message)

    async def _handle_command(self, command: str) -> None:
        parts = command.lower().strip().split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""

        if cmd_name == "/help":
            self.tui.show_help()
        elif cmd_name == "/clear":
            self.cli.agent.runtime.context_manager.clear()
            self.write_info("Conversation cleared.")
        elif cmd_name == "/config":
            self.write_assistant(
                "\n".join(
                    [
                        "## Current Configuration",
                        f"- Model: `{self.cli.config.model_name}`",
                        f"- Temperature: `{self.cli.config.temperature}`",
                        f"- Approval: `{self.cli.config.approval.value}`",
                        f"- Working Dir: `{self.cli.config.cwd}`",
                        f"- Max Turns: `{self.cli.config.max_turns}`",
                    ]
                )
            )
        elif cmd_name == "/model":
            if cmd_args:
                self.cli.config.model_name = cmd_args
                self.query_one("#model", Label).update(cmd_args)
                self.write_info(f"Model changed to {cmd_args}.")
            else:
                self.write_info(f"Current model: {self.cli.config.model_name}")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    self.cli.config.approval = ApprovalPolicy(cmd_args)
                    self.cli.agent.runtime.approval_manager.approval_policy = self.cli.config.approval
                    self.write_info(f"Approval policy changed to {cmd_args}.")
                except ValueError:
                    options = ", ".join(policy.value for policy in ApprovalPolicy)
                    self.write_error(f"Invalid approval policy. Valid options: {options}")
            else:
                self.write_info(f"Current approval policy: {self.cli.config.approval.value}")
        elif cmd_name == "/stats":
            stats = self.cli.agent.runtime.get_stats()
            lines = ["## Session Statistics"]
            lines.extend(f"- {key}: `{value}`" for key, value in stats.items())
            self.write_assistant("\n".join(lines))
        elif cmd_name == "/tools":
            tools = self.cli.agent.runtime.tool_registry.get_tools()
            names = ", ".join(tool.name for tool in tools)
            self.write_assistant(f"## Available Tools ({len(tools)})\n\n{names}")
        elif cmd_name == "/mcp":
            self.cli._print_mcp_snapshot()
        else:
            await self.cli._handle_command(command)

    @work(exclusive=True)
    async def run_agent(self, message: str) -> None:
        self.query_one("#input", Input).disabled = True
        try:
            if message.startswith("/"):
                await self._handle_command(message)
            else:
                await self.cli._process_message(message)
        except Exception as exc:
            self.write_error(str(exc))
        finally:
            self.query_one("#input", Input).disabled = False
            self.query_one("#input", Input).focus()
            self.clear_busy()

    def action_interrupt(self) -> None:
        self.write_info("Interrupt requested. Current operation will finish or fail normally.")


async def run_textual_interactive(cli: Any) -> None:
    app = PatTextualApp(cli)
    await app.run_async()
