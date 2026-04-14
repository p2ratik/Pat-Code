from pathlib import Path
from client.llm_client import LLMClient
from agent.agent import Agent
from agent.events import AgentEventType
from ui.tui import TUI, get_console
from config.config import Config
from config.loader import load_config
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
            )
            self.agent = agent

            while True:
                try:
                    user_input = console.input("\n[user]>[/user] ").strip()
                    if not user_input:
                        continue

                    # if user_input.startswith("/"):
                    #     should_continue = await self._handle_command(user_input)
                    #     if not should_continue:
                    #         break
                    #     continue

                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break

        console.print("\n[dim]Goodbye![/dim]")                 

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            tool_kind = None

        tool_kind = tool.kind.value

        return tool_kind
    
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

                content = event.data.get("content", "") # Ei content ta ek er por ek user dekhbe through the cli ui .
                self.tui.stream_assistant_delta(content=content)

            # elif event.type == AgentEventType.AGENT_START:
            #     self.tui.print_welcome(title="Pratik AI", lines = ["model : Claude Opus 6.9", "cwd : G/projects/AiAgent"] )

            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content", "")
                if assistant_stream:
                    self.tui.end_assistant()
                    assistant_stream = False        

            elif event.type == AgentEventType.AGENT_ERROR:
    
                error = event.data.get("error", "")
                console.print(f"\n [error] Bro ya fuckd up : {error} !")

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


@click.command()
@click.argument("prompt", required=False)
@click.option(
    '--cwd',
    '-c',
    type=click.Path(exists = True, file_okay = False, path_type=Path),
    help = "Current Working dir"
)
def main(prompt, cwd:Path|None):

    try:
        config = load_config(cwd=cwd)
    except Exception as e:
        console.print(f"\n[error] Config Error : {e}[/error]")

    errors = config.validate()

    if errors:
        for error in errors:
            console.print(f"Config Errors {error}")

        sys.exit(1)    

    cli = CLI(config=config)
    #message = [{'role':'user', 'content':'Write me a code for implementing quick sort algorithm in go language '}]
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())

main()

