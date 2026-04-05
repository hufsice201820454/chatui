"""Java AST GraphRAG (Neo4j) — Pydantic 모델."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

JavaGraphIntentLiteral = Literal[
    "METHOD_EXPLAIN",
    "CALL_CHAIN",
    "IMPACT_ANALYSIS",
    "DEPENDENCY_MAP",
    "CODE_SMELL",
    "REFACTOR_GUIDE",
]


class JavaGraphIntent(str, Enum):
    METHOD_EXPLAIN = "METHOD_EXPLAIN"
    CALL_CHAIN = "CALL_CHAIN"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    DEPENDENCY_MAP = "DEPENDENCY_MAP"
    CODE_SMELL = "CODE_SMELL"
    REFACTOR_GUIDE = "REFACTOR_GUIDE"


class QueryAnalysis(BaseModel):
    """QueryAnalyzer 출력."""

    intent: JavaGraphIntentLiteral
    target_class: Optional[str] = None
    target_method: Optional[str] = None
    depth: int = Field(default=2, ge=1, le=8)
    rule_matched: bool = Field(
        default=False,
        description="True if intent came from rule-based fast path",
    )

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, v: object) -> str:
        if v is None:
            return JavaGraphIntent.METHOD_EXPLAIN.value
        s = str(v).strip().upper().replace(" ", "_")
        valid = {x.value for x in JavaGraphIntent}
        if s in valid:
            return s
        return JavaGraphIntent.METHOD_EXPLAIN.value

    @field_validator("target_class", "target_method", mode="before")
    @classmethod
    def empty_to_none(cls, v: object) -> Optional[str]:
        if v is None or v == "" or v == "null":
            return None
        return str(v)


class GraphContextInput(BaseModel):
    """Neo4j 조회 결과 → ContextAssembler 입력 (설계 4.4)."""

    target_method_source: str = ""
    depth1_contexts: str = ""
    depth2_signatures: str = ""
    class_fqn: str = ""
    extends: str = ""
    implements: str = ""
    depends_on: str = ""
    cc: str = ""
    cogc: str = ""
    loc: str = ""
    fanout: str = ""


ExplainType = Literal["summary", "detail", "security"]
ChangeType = Literal["modify", "delete", "rename"]
RefactorFocus = Literal["complexity", "duplication", "coupling"]
