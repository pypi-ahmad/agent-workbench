"""Base structures and decorators for workbench tools."""

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert definition to OpenAI tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
