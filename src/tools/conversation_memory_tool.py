from typing import Dict, Any, Optional
from src.tools.base_tool import BaseTool
from src.conversation_memory import ConversationMemory

class ConversationMemoryTool(BaseTool):
    """
    Conversation Memory Tool for retrieving session turn history and turn counts.
    """

    def __init__(self, memory: Optional[ConversationMemory] = None):
        self.memory = memory

    @property
    def tool_name(self) -> str:
        return "conversation_memory"

    @property
    def tool_description(self) -> str:
        return "Inspects active session conversation history, recent questions, and message metrics."

    def validate(self, input_data: Dict[str, Any]) -> bool:
        return isinstance(input_data, dict)

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        mem_instance = input_data.get("memory") if input_data.get("memory") else self.memory

        if not mem_instance:
            return {
                "success": True,
                "tool_name": self.tool_name,
                "answer": "No active conversation memory instance found.",
                "history": [],
                "turn_count": 0
            }

        history = mem_instance.get_history()
        turn_count = mem_instance.get_turn_count()

        if not history:
            ans = "Conversation history is currently empty."
        else:
            ans = f"Conversation memory contains {len(history)} stored turn(s). First query: '{history[0]['user_query']}'."

        return {
            "success": True,
            "tool_name": self.tool_name,
            "answer": ans,
            "history": history,
            "turn_count": turn_count
        }
