from pathlib import Path
from typing import Any
from tools.base import Tool, ToolInvocation, ToolResult
import logging


logger = logging.getLogger(__name__)

class ToolRegistry:

    def __init__(self):
        self._tools : dict[str, Tool] = {}

    def register(self, tool : Tool)->None:
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool")

        self._tools[tool.name] = tool
        logger.debug(f"Registered tool : {tool.name}")

    def get(self, name: str)-> Tool | None:
        if name in self._tools:
            return self._tools[name]
        # Have to add mcp tools as well
        return None
    
    def unregister(self, name: str)->bool:
        if name in self._tools:
            del self._tools[name]
            return True
        
        return False
    
    def get_tools(self)->list[Tool]:
        tools = []
        for tool in self._tools.values():
            tools.append(tool)

        return tools    


    def get_schemas(self):
        return [tool.to_openai_schema() for tool in self.get_tools()]
        
