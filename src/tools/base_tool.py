from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """
    Abstract Base Class for all VARTA Agent Tools.
    Every tool must define a unique tool_name, tool_description, input validation, and execution logic.
    """

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Returns unique string identifier for the tool."""
        pass

    @property
    @abstractmethod
    def tool_description(self) -> str:
        """Returns human-readable description of tool capabilities."""
        pass

    @abstractmethod
    def validate(self, input_data: Dict[str, Any]) -> bool:
        """
        Validates input arguments before execution.
        Returns True if input is valid, False otherwise.
        """
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the tool operation with validated input_data.
        Returns a dictionary containing execution results, status, and output.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Returns standard tool metadata for discovery and registration."""
        return {
            "name": self.tool_name,
            "description": self.tool_description
        }
