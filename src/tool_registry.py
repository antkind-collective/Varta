from typing import Dict, List, Any, Optional
from src.tools.base_tool import BaseTool

class ToolRegistry:
    """
    Centralized Tool Registry for VARTA Agent.
    Manages registration, metadata discovery, and dynamic lookup of BaseTool implementations.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Registers a BaseTool instance into the registry."""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Cannot register object of type {type(tool)}. Must subclass BaseTool.")
        self._tools[tool.tool_name] = tool

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Retrieves a registered tool by its tool_name string."""
        return self._tools.get(tool_name)

    def has_tool(self, tool_name: str) -> bool:
        """Returns True if the tool_name is registered in the registry."""
        return tool_name in self._tools

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns a list of metadata for all registered tools."""
        return [tool.get_metadata() for tool in self._tools.values()]

    def list_tool_names(self) -> List[str]:
        """Returns a list of all registered tool names."""
        return list(self._tools.keys())
