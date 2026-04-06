"""Text2Cypher Few-Shot 예시 모음.

실제 MES 그래프 데이터에서 추출한 패턴 기반:
  SystemApiController#getMesPrintingPrograms(Map)
    -[:CALLS]->
  Casting#MapCast(Map, String[])

배치 위치: backend/src/java_ast_graphrag/graphrag/few_shot_examples.py
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FewShotExample:
    intent: str
    question: str
    cypher: str


FEW_SHOT_EXAMPLES: list[FewShotExample] = [

    # ── METHOD_EXPLAIN ──────────────────────────────────────────
    FewShotExample(
        intent="METHOD_EXPLAIN",
        question="getMesPrintingPrograms 메서드가 뭘 하는 메서드야?",
        cypher="""\
MATCH (c:`Class`)-[:DECLARES]->(m:`Method`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH c, m LIMIT 1
OPTIONAL MATCH (m)-[:CALLS]->(d:`Method`)
RETURN c.fqn                                                  AS class_fqn,
       coalesce(m.signature, m.name)                          AS method_signature,
       coalesce(m.source, m.body, '')                         AS method_source,
       coalesce(toString(m.cyclomaticComplexity), '')          AS cc,
       coalesce(toString(m.cognitiveComplexity), '')           AS cogc,
       coalesce(toString(m.loc), toString(m.lineCount), '')    AS loc,
       coalesce(toString(m.fanOut), '')                        AS fanout,
       coalesce(toString(c.extends), '')                       AS extends,
       coalesce(toString(c.implements), '')                    AS implements,
       coalesce(toString(c.dependsOn), '')                     AS depends_on,
       collect(DISTINCT coalesce(d.signature, d.name))         AS callees""",
    ),

    # ── CALL_CHAIN ──────────────────────────────────────────────
    FewShotExample(
        intent="CALL_CHAIN",
        question="getMesPrintingPrograms의 호출 체인을 보여줘",
        cypher="""\
MATCH (c:`Class`)-[:DECLARES]->(m:`Method`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH m LIMIT 1
OPTIONAL MATCH path = (m)-[:CALLS*1..3]->(callee:`Method`)
RETURN m.signature AS root,
       [node IN nodes(path) | coalesce(node.signature, node.name)] AS call_chain,
       length(path) AS depth
ORDER BY depth
LIMIT 50""",
    ),

    # ── IMPACT_ANALYSIS ─────────────────────────────────────────
    FewShotExample(
        intent="IMPACT_ANALYSIS",
        question="MapCast를 수정하면 어디에 영향을 줘?",
        cypher="""\
MATCH (c:`Class`)-[:DECLARES]->(m:`Method`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH m LIMIT 1
OPTIONAL MATCH (caller:`Method`)-[:CALLS*1..3]->(m)
OPTIONAL MATCH (callerClass:`Class`)-[:DECLARES]->(caller)
RETURN m.signature                            AS target,
       collect(DISTINCT caller.signature)     AS impacted_methods,
       collect(DISTINCT callerClass.fqn)      AS impacted_classes
LIMIT 100""",
    ),

    # ── DEPENDENCY_MAP ──────────────────────────────────────────
    FewShotExample(
        intent="DEPENDENCY_MAP",
        question="SystemApiController가 의존하는 클래스 목록을 보여줘",
        cypher="""\
MATCH (c:`Class`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c LIMIT 1
OPTIONAL MATCH (c)-[:DECLARES]->(m:`Method`)-[:CALLS]->(callee:`Method`)
OPTIONAL MATCH (calleeClass:`Class`)-[:DECLARES]->(callee)
WITH c,
     [x IN split(coalesce(toString(c.dependsOn), ''), ';')
      WHERE size(trim(x)) > 0 | trim(x)] AS import_deps,
     collect(DISTINCT calleeClass.fqn)   AS call_deps
RETURN c.fqn      AS class_fqn,
       import_deps AS import_dependencies,
       call_deps   AS call_dependencies""",
    ),

    # ── CODE_SMELL ──────────────────────────────────────────────
    FewShotExample(
        intent="CODE_SMELL",
        question="Casting 클래스에 복잡도 높은 메서드가 있어?",
        cypher="""\
MATCH (c:`Class`)-[:DECLARES]->(m:`Method`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
RETURN m.signature                  AS method,
       m.cyclomaticComplexity        AS cc,
       m.cognitiveComplexity         AS cogc,
       m.loc                         AS loc,
       m.fanOut                      AS fan_out
ORDER BY m.cyclomaticComplexity DESC, m.cognitiveComplexity DESC
LIMIT 20""",
    ),

    # ── REFACTOR_GUIDE ──────────────────────────────────────────
    FewShotExample(
        intent="REFACTOR_GUIDE",
        question="MapCast 리팩토링 방법을 알려줘",
        cypher="""\
MATCH (c:`Class`)-[:DECLARES]->(m:`Method`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH c, m LIMIT 1
OPTIONAL MATCH (m)-[:CALLS]->(callee:`Method`)
OPTIONAL MATCH (sibling:`Method`)<-[:DECLARES]-(c)
WHERE sibling.id <> m.id
RETURN m.signature                                                  AS target_method,
       coalesce(m.source, m.body, '')                               AS source,
       m.cyclomaticComplexity                                        AS cc,
       m.cognitiveComplexity                                         AS cogc,
       m.loc                                                         AS loc,
       m.fanOut                                                      AS fan_out,
       collect(DISTINCT coalesce(callee.signature, callee.name))    AS callees,
       collect(DISTINCT coalesce(sibling.signature, sibling.name))[..10] AS sibling_methods""",
    ),
]


def build_few_shot_block(intent: str, *, max_examples: int = 2) -> str:
    """주어진 intent에 해당하는 few-shot 예시를 프롬프트 주입용 문자열로 반환.

    같은 intent 예시를 우선하고, 부족하면 이종 intent로 보충.
    """
    same   = [e for e in FEW_SHOT_EXAMPLES if e.intent == intent]
    others = [e for e in FEW_SHOT_EXAMPLES if e.intent != intent]
    selected = (same + others)[:max_examples]

    if not selected:
        return ""

    parts: list[str] = ["[Few-Shot 예시 — 아래 패턴을 참고해 Cypher를 작성하세요]\n"]
    for i, ex in enumerate(selected, 1):
        parts.append(
            f"예시 {i} (intent={ex.intent})\n"
            f"질의: {ex.question}\n"
            f"Cypher:\n{ex.cypher}\n"
        )
    return "\n".join(parts)
