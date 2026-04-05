"""PendingCall → ExtractedCall (클래스/메서드 인덱스 기준)."""
from __future__ import annotations

from src.java_ast_graphrag.graphrag.ingestion_pipeline.models import (
    ExtractedCall,
    ExtractedMethod,
    PendingCall,
    WorkspaceGraph,
)


def _resolve_qualifier_to_class_fqn(
    qualifier: str | None,
    caller_class_fqn: str,
    import_map: dict[str, str],
    known_fqns: set[str],
) -> str | None:
    if qualifier is None or qualifier == "this":
        return caller_class_fqn
    if qualifier == "super":
        return None
    if qualifier in import_map:
        full = import_map[qualifier]
        if full in known_fqns:
            return full
    jl = f"java.lang.{qualifier}"
    if jl in known_fqns:
        return jl
    parent = caller_class_fqn
    while parent:
        cand = f"{parent}.{qualifier}"
        if cand in known_fqns:
            return cand
        if "." not in parent:
            break
        parent = parent.rsplit(".", 1)[0]
    if qualifier in known_fqns:
        return qualifier
    return None


def _pick_callee(
    target_class_fqn: str,
    member: str,
    arg_count: int,
    methods: list[ExtractedMethod],
) -> str | None:
    cands = [m for m in methods if m.class_fqn == target_class_fqn and m.name == member]
    if not cands:
        return None
    exact = [m for m in cands if m.param_count == arg_count]
    if len(exact) == 1:
        return exact[0].id
    if exact:
        return exact[0].id
    return cands[0].id


def resolve_calls(workspace: WorkspaceGraph) -> list[ExtractedCall]:
    methods = workspace.all_methods()
    known_fqns = {c.fqn for c in workspace.all_classes()}
    out: list[ExtractedCall] = []
    seen: set[tuple[str, str]] = set()

    for f in workspace.files:
        for p in f.pending_calls:
            if p.qualifier == "super":
                continue
            target = _resolve_qualifier_to_class_fqn(
                p.qualifier,
                p.caller_class_fqn,
                p.import_map,
                known_fqns,
            )
            if target is None:
                continue
            callee_id = _pick_callee(target, p.member, p.arg_count, methods)
            if callee_id is None:
                continue
            key = (p.caller_method_id, callee_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                ExtractedCall(
                    caller_method_id=p.caller_method_id,
                    callee_method_id=callee_id,
                )
            )
    return out
