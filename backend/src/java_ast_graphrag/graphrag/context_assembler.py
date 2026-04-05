"""그래프 탐색 결과 → LLM용 단일 컨텍스트 문자열 + 토큰 예산 (문서: ContextAssembler)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from config import settings

from src.java_ast_graphrag.graphrag.context_template import CONTEXT_TEMPLATE
from src.java_ast_graphrag.models import GraphContextInput

logger = logging.getLogger(__name__)

_FIELD_RATIOS: dict[str, float] = {
    "target_method_source": 0.15,
    "depth1_contexts": 0.35,
    "depth2_signatures": 0.30,
    "class_fqn": 0.025,
    "extends": 0.025,
    "implements": 0.025,
    "depends_on": 0.025,
    "cc": 0.025,
    "cogc": 0.025,
    "loc": 0.025,
    "fanout": 0.025,
}

_TRIM_ORDER: tuple[str, ...] = (
    "fanout",
    "loc",
    "cogc",
    "cc",
    "depends_on",
    "implements",
    "extends",
    "class_fqn",
    "depth2_signatures",
    "depth1_contexts",
    "target_method_source",
)


def _default_token_counter(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class ContextAssembler:
    max_tokens: int | None = None
    token_counter: Callable[[str], int] | None = None

    def __post_init__(self) -> None:
        self._count = self.token_counter or _default_token_counter
        self._budget = self.max_tokens or int(
            getattr(settings, "JAVA_GRAPHRAG_MAX_CONTEXT_TOKENS", 8000)
        )

    def _trim_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        if not text:
            return text
        if self._count(text) <= max_tokens:
            return text
        lo, hi = 0, len(text)
        best = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            chunk = text[:mid]
            if self._count(chunk) <= max_tokens:
                best = chunk
                lo = mid + 1
            else:
                hi = mid - 1
        if len(best) < len(text):
            return best.rstrip() + "\n…(truncated)"
        return best

    def _field_text(self, name: str, ctx: GraphContextInput) -> str:
        return str(getattr(ctx, name, "") or "")

    def build(self, ctx: GraphContextInput) -> str:
        fields: dict[str, str] = {k: self._field_text(k, ctx) for k in _FIELD_RATIOS}

        alloc = {k: max(0, int(self._budget * r)) for k, r in _FIELD_RATIOS.items()}
        trimmed = {k: self._trim_to_tokens(fields[k], alloc[k]) for k in _FIELD_RATIOS}

        def total_est() -> int:
            body = CONTEXT_TEMPLATE.format(**trimmed)
            return self._count(body)

        guard = 0
        while total_est() > self._budget and guard < 80:
            guard += 1
            over = total_est() - self._budget
            done = False
            for name in _TRIM_ORDER:
                if over <= 0:
                    break
                cur = trimmed[name]
                if not cur:
                    continue
                ct = self._count(cur)
                new_max = max(0, ct - over)
                new_s = self._trim_to_tokens(cur, new_max)
                if new_s != cur:
                    trimmed[name] = new_s
                    done = True
                    break
            if not done:
                break

        out = CONTEXT_TEMPLATE.format(**trimmed)
        if self._count(out) > self._budget:
            out = self._trim_to_tokens(out, self._budget)
        logger.debug(
            "ContextAssembler: budget=%d est_tokens=%d",
            self._budget,
            self._count(out),
        )
        return out


def assemble_context(
    ctx: GraphContextInput,
    *,
    max_tokens: int | None = None,
    token_counter: Callable[[str], int] | None = None,
) -> str:
    return ContextAssembler(max_tokens=max_tokens, token_counter=token_counter).build(ctx)
