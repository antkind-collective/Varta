import sys
import platform
from typing import Dict, Any, Optional
from src.tools.base_tool import BaseTool

class SystemInfoTool(BaseTool):
    """
    System Information Tool for reporting runtime model, provider, token budget, and platform telemetry.
    """

    def __init__(
        self,
        provider: str = "OpenAIAdapter",
        model: str = "gpt-4o-mini",
        max_context_tokens: int = 2048
    ):
        self.provider = provider
        self.model = model
        self.max_context_tokens = max_context_tokens

    @property
    def tool_name(self) -> str:
        return "system_info"

    @property
    def tool_description(self) -> str:
        return "Returns system runtime details, active LLM provider, model name, token budget, and session status."

    def validate(self, input_data: Dict[str, Any]) -> bool:
        return isinstance(input_data, dict)

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        session_id = input_data.get("session_id", "N/A")
        provider_name = input_data.get("provider", self.provider)
        model_name = input_data.get("model", self.model)

        info = {
            "session_id": session_id,
            "llm_provider": provider_name,
            "active_model": model_name,
            "max_context_tokens": self.max_context_tokens,
            "python_version": sys.version.split()[0],
            "operating_system": platform.system()
        }

        formatted_answer = (
            f"**System Status & Environment Info**:\n"
            f"- **LLM Provider**: {info['llm_provider']}\n"
            f"- **Active Model**: {info['active_model']}\n"
            f"- **Context Token Budget**: {info['max_context_tokens']} tokens\n"
            f"- **Session ID**: {info['session_id']}\n"
            f"- **OS Environment**: {info['operating_system']} (Python {info['python_version']})"
        )

        return {
            "success": True,
            "tool_name": self.tool_name,
            "answer": formatted_answer,
            "system_info": info,
            "confidence": {
                "score": 1.0,
                "level": "HIGH",
                "retrieval_support": "SYSTEM_METADATA",
                "context_coverage_pct": 100.0
            },
            "citations": []
        }
