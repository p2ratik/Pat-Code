from client.llm_client import LLMClient
from agent.agent import Agent
from agent.events import AgentEventType
from ui.tui import TUI, get_console
import sys
import asyncio
import click

console = get_console()

class CLI:
    def __init__(self):
        self.agent : Agent | None = None
        self.tui = TUI(console)
            
    async def run_single(self, message):
        async with Agent() as agent:
            self.agent = agent
            return await self._process_message(message)    

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

            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content", "")
                if assistant_stream:
                    self.tui.end_assistant()
                    assistant_stream = False

            elif event.type == AgentEventType.AGENT_ERROR:
                print("bal")
                error = event.data.get("error", "")
                console.print(f"\n [error] Bro ya fuckd up : {error} !")

        return final_response


@click.command()
@click.argument("prompt", required=False)
def main(prompt):

    cli = CLI()
 
    #message = [{'role':'user', 'content':'Write me a code for implementing quick sort algorithm in go language '}]
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)


main()

