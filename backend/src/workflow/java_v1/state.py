"""Java GraphRAG LangGraph 상태."""
from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict


class JavaGraphRAGState(TypedDict, total=False):
    user_query: str
    tool: str
    explain_type: str
    change_type: str
    focus: str
    target_signature: str
    dependency_list: str
    rule_confidence_threshold: float
    analysis: dict[str, Any]
    assembled_context: str
    raw_graph: str
    result: Optional[str]
    error: Optional[str]
