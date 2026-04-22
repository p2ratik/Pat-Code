from pathlib import Path
from agent.persistence import PersistenceManager, SessionSnapshot
from agent.session import Session
from client.llm_client import LLMClient
from agent.agent import Agent
from agent.events import AgentEventType
from ui.tui1 import TUI, get_console
from config.config import ApprovalPolicy, Config
from config.loader import load_config
from config.credentials import (
    set_credential,
    get_credential,
    delete_credential,
    APIKEY_KEY,
    BASEURL_KEY,
)
import sys
import asyncio
import click

console = get_console()

class CLI:
    def __init__(self, config:Config):
        self.agent : Agent | None = None
        self.config = config
        self.tui = TUI(console, config)

            
    async def run_single(self, message):
        async with Agent(self.config) as agent:
            self.agent = agent
            return await self._process_message(message)    
        
    async def run_interactive(self) -> str | None:

        async with Agent(self.config) as agent:
            self.tui.print_welcome(
                title="PAT",
                version="0.0.1",
                cwd=self.config.cwd,
                model=self.config.model_name,
            )
            self.agent = agent
            self._print_mcp_snapshot()

            while True:
                try:
                    user_input = console.input("\n[user]>[/user] ").strip()
                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = await self._handle_command(user_input)
                        if not should_continue:
                            break
                        continue

                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break

        console.print("\n[dim]Goodbye![/dim]")                 

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            return None

        kind = getattr(tool, "kind", None)
        return getattr(kind, "value", None)

    def _print_mcp_snapshot(self) -> None:
        if not self.agent:
            return

        servers = self.agent.session.mcp_manager.get_all_servers()
        mcp_tool_names = sorted(
            [tool.name for tool in self.agent.session.tool_registry.connected_mcp_servers]
        )
        self.tui.print_mcp_status(servers, mcp_tool_names)

    async def _handle_command(self, command: str) -> bool:

        cmd = command.lower().strip()
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""
        if cmd_name == "/exit" or cmd_name == "/quit":
            return False
        elif cmd_name == "/help":
            self.tui.show_help()
        elif cmd_name == "/clear":
            self.agent.session.context_manager.clear()
            console.print("[success]Conversation cleared [/success]")
        elif cmd_name == "/config":
            console.print("\n[bold]Current Configuration[/bold]")
            console.print(f"  Model: {self.config.model_name}")
            console.print(f"  Temperature: {self.config.temperature}")
            console.print(f"  Approval: {self.config.approval.value}")
            console.print(f"  Working Dir: {self.config.cwd}")
            console.print(f"  Max Turns: {self.config.max_turns}")
            # console.print(f"  Hooks Enabled: {self.config.hooks_enabled}")
        elif cmd_name == "/model":
            if cmd_args:
                self.config.model_name = cmd_args
                console.print(f"[success]Model changed to: {cmd_args} [/success]")
            else:
                console.print(f"Current model: {self.config.model_name}")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    approval = ApprovalPolicy(cmd_args)
                    self.config.approval = approval
                    console.print(
                        f"[success]Approval policy changed to: {cmd_args} [/success]"
                    )
                except:
                    console.print(
                        f"[error]Incorrect approval policy: {cmd_args} [/error]"
                    )
                    console.print(
                        f"Valid options: {', '.join(p.value for p in ApprovalPolicy)}"
                    )
            else:
                console.print(f"Current approval policy: {self.config.approval.value}")
        elif cmd_name == "/stats":
            stats = self.agent.session.get_stats()
            console.print("\n[bold]Session Statistics [/bold]")
            for key, value in stats.items():
                console.print(f"   {key}: {value}")
        elif cmd_name == "/tools":
            tools = self.agent.session.tool_registry.get_tools()
            console.print(f"\n[bold]Available tools ({len(tools)}) [/bold]")
            for tool in tools:
                console.print(f"  • {tool.name}")
        elif cmd_name == "/mcp":
            mcp_servers = self.agent.session.mcp_manager.get_all_servers()
            console.print(f"\n[bold]MCP Servers ({len(mcp_servers)}) [/bold]")
            for server in mcp_servers:
                status = server["status"]
                status_color = "green" if status == "connected" else "red"
                console.print(
                    f"  • {server['name']}: [{status_color}]{status}[/{status_color}] ({server['tools']} tools)"
                )
        elif cmd_name == "/save":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            persistence_manager.save_session(session_snapshot)
            console.print(
                f"[success]Session saved: {self.agent.session.session_id}[/success]"
            )
        elif cmd_name == "/sessions":
            persistence_manager = PersistenceManager()
            sessions = persistence_manager.list_sessions()
            console.print("\n[bold]Saved Sessions[/bold]")
            for s in sessions:
                console.print(
                    f"  • {s['session_id']} (turns: {s['turn_count']}, updated: {s['updated_at']})"
                )
        elif cmd_name == "/resume":
            if not cmd_args:
                console.print(f"[error]Usage: /resume <session_id> [/error]")
            else:
                persistence_manager = PersistenceManager()
                snapshot = persistence_manager.load_session(cmd_args)
                if not snapshot:
                    console.print(f"[error]Session does not exist [/error]")
                else:
                    session = Session(
                        config=self.config,
                    )
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""), msg.get("tool_calls")
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""), msg.get("content", "")
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}[/success]"
                    )
        elif cmd_name == "/checkpoint":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            checkpoint_id = persistence_manager.save_checkpoint(session_snapshot)
            console.print(f"[success]Checkpoint created: {checkpoint_id}[/success]")
        elif cmd_name == "/listcheckpoints":
            persistence_manager = PersistenceManager()
            checkpoints = persistence_manager.list_checkpoints(self.agent.session.session_id)
            console.print("\n[bold]Saved Checkpoints for current Session[/bold]")
            for s in checkpoints:
                console.print(
                    f"  • {s['checkpoint_id']} (turns: {s['turn_count']}, updated: {s['updated_at']})"
                )                 
            
        elif cmd_name == "/restore":
            if not cmd_args:
                console.print(f"[error]Usage: /restore <checkpoint_id> [/error]")
            else:
                persistence_manager = PersistenceManager()
                snapshot = persistence_manager.load_checkpoint(cmd_args)
                if not snapshot:
                    console.print(f"[error]Checkpoint does not exist [/error]")
                else:
                    session = Session(
                        config=self.config,
                    )
                    await session.initialize()
                    session.session_id = snapshot.session_id
                    session.created_at = snapshot.created_at
                    session.updated_at = snapshot.updated_at
                    session.turn_count = snapshot.turn_count
                    session.context_manager.total_usage = snapshot.total_usage

                    for msg in snapshot.messages:
                        if msg.get("role") == "system":
                            continue
                        elif msg["role"] == "user":
                            session.context_manager.add_user_message(
                                msg.get("content", "")
                            )
                        elif msg["role"] == "assistant":
                            session.context_manager.add_assistant_message(
                                msg.get("content", ""), msg.get("tool_calls")
                            )
                        elif msg["role"] == "tool":
                            session.context_manager.add_tool_result(
                                msg.get("tool_call_id", ""), msg.get("content", "")
                            )

                    await self.agent.session.client.close()
                    await self.agent.session.mcp_manager.shutdown()

                    self.agent.session = session
                    console.print(
                        f"[success]Resumed session: {session.session_id}, checkpoint: {cmd_args}[/success]"
                    )
        else:
            console.print(f"[error]Unknown command: {cmd_name}[/error]")

        return True
    
    # Runs only once .
    async def _process_message(self, message : str | None = None):
        
        if not self.agent:
            return None
        assistant_stream = False
        final_response = ""

        async for event in self.agent.run(message=message):
            
            
            if event.type == AgentEventType.TEXT_DELTA:
                if not assistant_stream:
                    self.tui.begin_assistant()
                    assistant_stream = True

                content = event.data.get("content", "") 
                self.tui.stream_assistant_delta(content=content)


            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content", "")
                if assistant_stream:
                    self.tui.end_assistant()
                    assistant_stream = False        

            elif event.type == AgentEventType.AGENT_ERROR:
    
                error = event.data.get("error", "")
                console.print(f"\n[error]Agent error: {error}[/error]")

            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_start(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("arguments", {}),
                )

            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("diff"),
                    event.data.get("truncated", False),
                    event.data.get("exit_code"),
                )

        return final_response


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--prompt", "-p",
    default=None,
    help="Run a single prompt and exit (non-interactive mode).",
)
@click.option(
    '--cwd',
    '-c',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
def main(ctx, prompt, cwd: Path | None):
    """PAT — your AI coding agent."""
    # If a sub-command is about to run (e.g. `agent configure …`), skip the
    # normal agent startup entirely.
    if ctx.invoked_subcommand is not None:
        return

    try:
        config = load_config(cwd=cwd)
    except Exception as e:
        console.print(f"\n[error] Config Error : {e}[/error]")
        sys.exit(1)

    errors = config.validate()

    if errors:
        for error in errors:
            console.print(f"Config Errors {error}")
        sys.exit(1)

    cli = CLI(config=config)

    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())


# ---------------------------------------------------------------------------
# `agent configure` sub-command group
# ---------------------------------------------------------------------------

@main.group("configure", help="Store or view credentials in the OS keyring.")
def configure_group():
    pass


@configure_group.command("apikey", help="Store your API key in the OS keyring.")
@click.argument("value")
def configure_apikey(value: str):
    set_credential(APIKEY_KEY, value)
    masked = value[:6] + "*" * max(0, len(value) - 6)
    console.print(f"[green][OK][/green] API key saved to keyring ({masked})")


@configure_group.command("baseurl", help="Store the API base URL in the OS keyring.")
@click.argument("value")
def configure_baseurl(value: str):
    set_credential(BASEURL_KEY, value)
    console.print(f"[green][OK][/green] Base URL saved to keyring: {value}")


@configure_group.command("show", help="Show currently stored credentials.")
def configure_show():
    api_key  = get_credential(APIKEY_KEY)
    base_url = get_credential(BASEURL_KEY)

    console.print("[bold]Stored credentials (keyring)[/bold]")
    if api_key:
        masked = api_key[:6] + "*" * max(0, len(api_key) - 6)
        console.print(f"  apikey  : {masked}")
    else:
        console.print("  apikey  : [dim]not set[/dim]")

    if base_url:
        console.print(f"  baseurl : {base_url}")
    else:
        console.print("  baseurl : [dim]not set[/dim]")


@configure_group.command("delete", help="Delete a stored credential from the OS keyring.")
@click.argument("name", type=click.Choice(["apikey", "baseurl"], case_sensitive=False))
def configure_delete(name: str):
    key = APIKEY_KEY if name.lower() == "apikey" else BASEURL_KEY
    removed = delete_credential(key)
    if removed:
        console.print(f"[green][OK][/green] '{name}' removed from keyring.")
    else:
        console.print(f"[yellow]'{name}' was not found in keyring.[/yellow]")


if __name__ == "__main__":
    main()
