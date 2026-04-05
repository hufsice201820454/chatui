"""설계 4.4 토큰 비중 — 섹션 ID 매핑.

비중 합계 100%: target_method 15%, depth1 35%, depth2 30%, class_meta 10%, metrics 10%.
"""
from __future__ import annotations

SECTION_BUDGET_RATIOS: dict[str, float] = {
    "target_method_source": 0.15,
    "depth1_contexts": 0.35,
    "depth2_signatures": 0.30,
    "class_structure": 0.10,
    "metrics": 0.10,
}

TRIM_PRIORITY: tuple[str, ...] = (
    "metrics",
    "class_structure",
    "depth2_signatures",
    "depth1_contexts",
    "target_method_source",
)

CONTEXT_TEMPLATE = """
[대상 메서드]
{target_method_source}

[직접 호출 메서드 - depth 1]
{depth1_contexts}

[간접 연관 메서드 - depth 2 (시그니처만)]
{depth2_signatures}

[클래스 구조 요약]
- 소속: {class_fqn}
- 상속: {extends}
- 구현: {implements}
- 의존: {depends_on}

[복잡도 메트릭]
CC={cc}, CogC={cogc}, LOC={loc}, Fan-out={fanout}
""".strip()
