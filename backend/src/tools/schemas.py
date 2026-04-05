"""
Tool definition schemas – OpenAI Function Calling-compatible JSON Schema (BE-TOOL-03).
A tool is defined as:
  {
    "name": str,
    "description": str,
    "input_schema": {          # JSON Schema object
      "type": "object",
      "properties": { ... },
      "required": [...]
    }
  }
OpenAI wraps it in {"type":"function","function":{...}}.
"""
from pydantic import BaseModel, Field
from typing import Any, Optional


class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: ToolInputSchema

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_dump(exclude_none=True),
            },
        }
