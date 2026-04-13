from __future__ import annotations

from dataclasses import dataclass

from src.java_ast_graphrag.ingestion.parser.ast_parser import ExtractedMethod, PendingCall


@dataclass
class ExtractedCall:
    caller_method_id: str
    callee_method_id: str


def resolve_calls(methods: list[ExtractedMethod], pending_calls: list[PendingCall]) -> list[ExtractedCall]:
    methods_by_class: dict[str, list[ExtractedMethod]] = {}
    for m in methods:
        methods_by_class.setdefault(m.class_fqn, []).append(m)

    by_class_and_name: dict[tuple[str, str], list[ExtractedMethod]] = {}
    for m in methods:
        by_class_and_name.setdefault((m.class_fqn, m.name), []).append(m)

    resolved: list[ExtractedCall] = []
    seen: set[tuple[str, str]] = set()
    for p in pending_calls:
        targets: list[ExtractedMethod] = []
        if p.qualifier:
            q = p.qualifier.split(".")[-1]
            class_fqn = p.import_map.get(q)
            if class_fqn:
                targets = by_class_and_name.get((class_fqn, p.member), [])

        if not targets:
            local = methods_by_class.get(p.caller_class_fqn, [])
            targets = [m for m in local if m.name == p.member]

        if not targets:
            continue
        target = targets[0]
        key = (p.caller_method_id, target.id)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(ExtractedCall(caller_method_id=p.caller_method_id, callee_method_id=target.id))
    return resolved

