"""Intent/스키마별 Cypher 템플릿.

AST 그래프는 NEO4J_LABEL_CLASS / NEO4J_LABEL_METHOD 및 관계(:DECLARES, :CALLS)를 스키마에 맞게 조정.
"""
from __future__ import annotations


def resolve_target_method(class_label: str, method_label: str) -> str:
    return f"""
MATCH (c:`{class_label}`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c LIMIT 1
MATCH (c)-[:DECLARES]->(m:`{method_label}`)
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
RETURN c.fqn AS class_fqn,
       coalesce(m.signature, m.name) AS method_signature,
       coalesce(m.source, m.body, '') AS method_source,
       coalesce(toString(m.cyclomaticComplexity), '') AS cc,
       coalesce(toString(m.cognitiveComplexity), '') AS cogc,
       coalesce(toString(m.loc), toString(m.lineCount), '') AS loc,
       coalesce(toString(m.fanOut), '') AS fanout,
       coalesce(toString(c.extends), '') AS extends,
       coalesce(toString(c.implements), '') AS implements,
       coalesce(toString(c.dependsOn), '') AS depends_on
LIMIT 1
""".strip()


def callees_depth1(class_label: str, method_label: str) -> str:
    return f"""
MATCH (c:`{class_label}`)-[:DECLARES]->(m:`{method_label}`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH m LIMIT 1
OPTIONAL MATCH (m)-[:CALLS]->(d:`{method_label}`)
RETURN collect(DISTINCT coalesce(d.signature, d.name, elementId(d))) AS callees
""".strip()


def callees_depth2_signatures(class_label: str, method_label: str, max_hops: int) -> str:
    hops = max(2, min(max_hops, 8))
    return f"""
MATCH (c:`{class_label}`)-[:DECLARES]->(m:`{method_label}`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c, m
WHERE $tm IS NULL OR toLower(m.name) = toLower($tm)
WITH m LIMIT 1
OPTIONAL MATCH p = (m)-[:CALLS*2..{hops}]->(x:`{method_label}`)
WHERE length(p) >= 2
RETURN collect(DISTINCT coalesce(x.signature, x.name)) AS deep_sigs
LIMIT 200
""".strip()


def dependency_neighbors(class_label: str) -> str:
    """적재 스키마는 Class.dependsOn 문자열(; 구분)만 있음 — DEPENDS_ON/USES 엣지 없음."""
    return f"""
MATCH (c:`{class_label}`)
WHERE $tc IS NULL OR toLower(c.name) = toLower($tc)
   OR ($tc IS NOT NULL AND (c.fqn ENDS WITH ('.' + $tc) OR c.fqn = $tc))
WITH c LIMIT 1
WITH trim(coalesce(toString(c.dependsOn), '')) AS raw
RETURN [x IN split(raw, ';') WHERE size(trim(x)) > 0 | trim(x)] AS deps
LIMIT 1
""".strip()


def raw_paths_for_summary(class_label: str, method_label: str, max_hops: int) -> str:
    hops = max(1, min(max_hops, 8))
    return f"""
MATCH (c:`{class_label}`)-[:DECLARES]->(m:`{method_label}`)
WHERE ($tc IS NULL OR toLower(c.name) = toLower($tc))
AND ($tm IS NULL OR toLower(m.name) = toLower($tm))
WITH m LIMIT 1
OPTIONAL MATCH (m)-[:CALLS]->(d:`{method_label}`)
OPTIONAL MATCH (m)-[:CALLS*2..{hops}]->(x:`{method_label}`)
WITH m,
     collect(DISTINCT coalesce(d.signature, d.name)) AS depth1,
     collect(DISTINCT coalesce(x.signature, x.name)) AS deeper
RETURN coalesce(m.signature, m.name) AS root,
       depth1 AS callees_depth1,
       deeper AS callees_indirect
""".strip()
