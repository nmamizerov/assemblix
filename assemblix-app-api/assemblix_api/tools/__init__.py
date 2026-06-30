# /tools/__init__.py

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Tool parameter definition"""

    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = False
    enum: list[str] | None = None


class BaseTool(ABC):
    """
    Base class for all tools/functions that can be used by LLM agents.

    Each tool must implement:
    - name: Unique identifier for the tool
    - description: What the tool does (used by LLM to decide when to call it)
    - parameters: List of parameters the tool accepts
    - execute: Async method that performs the tool's action
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does (for LLM)"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """List of parameters this tool accepts"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters

        Returns:
            Tool execution result (will be serialized to JSON for LLM)
        """
        pass

    def to_openai_format(self) -> dict[str, Any]:
        """
        Convert tool definition to OpenAI Function Calling format.

        This format is compatible with:
        - OpenAI (native)
        - Anthropic Claude (via LiteLLM conversion)
        - Google Gemini (via LiteLLM conversion)
        - Other providers (via LiteLLM)

        Returns:
            Tool definition in OpenAI format
        """
        properties: dict[str, dict[str, Any]] = {}
        required: list[str] = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


# Side-effect import: registers built-in tools in ToolRegistry.
from assemblix_api.tools import tavily_search_tool as _tavily  # noqa: E402,F401
