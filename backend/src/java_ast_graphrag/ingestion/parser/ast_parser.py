from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import javalang
from javalang import tree

from src.java_ast_graphrag.ingestion.parser.complexity_analyzer import (
    calculate_cognitive_complexity,
    calculate_cyclomatic_complexity,
)


@dataclass
class ExtractedClass:
    fqn: str
    name: str
    file_rel_path: str


@dataclass
class ExtractedMethod:
    id: str
    class_fqn: str
    name: str
    signature: str
    source: str
    body: str
    line_count: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    loc: int
    fan_out: int


@dataclass
class PendingCall:
    caller_method_id: str
    caller_class_fqn: str
    member: str
    qualifier: str | None
    arg_count: int
    import_map: dict[str, str]


@dataclass
class ParseOutcome:
    relative_path: str
    classes: list[ExtractedClass] = field(default_factory=list)
    methods: list[ExtractedMethod] = field(default_factory=list)
    pending_calls: list[PendingCall] = field(default_factory=list)
    error: str | None = None


def _class_fqn(package_name: str, class_name: str) -> str:
    return f"{package_name}.{class_name}" if package_name else class_name


def _method_signature(name: str, parameters: list[Any]) -> str:
    parts: list[str] = []
    for p in parameters or []:
        t = getattr(p, "type", None)
        t_name = getattr(t, "name", None) or "var"
        parts.append(t_name)
    return f"{name}({', '.join(parts)})"


def _method_id(class_fqn: str, name: str, parameters: list[Any]) -> str:
    return f"{class_fqn}#{_method_signature(name, parameters)}"


def _slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
    start = max(1, start_line)
    end = min(len(lines), max(start, end_line))
    return "\n".join(lines[start - 1 : end])


def _collect_invocations(body: Any) -> list[tree.MethodInvocation]:
    out: list[tree.MethodInvocation] = []

    def walk(node: Any) -> None:
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, list):
            for x in node:
                walk(x)
            return
        if isinstance(node, tree.MethodInvocation):
            out.append(node)
        if hasattr(node, "__dict__"):
            for v in vars(node).values():
                walk(v)

    walk(body)
    return out


def _import_map(imports: list[tree.Import]) -> dict[str, str]:
    out: dict[str, str] = {}
    for imp in imports or []:
        if getattr(imp, "wildcard", False):
            continue
        if not imp.path:
            continue
        out[imp.path.rsplit(".", 1)[-1]] = imp.path
    return out


def parse_java_file(relative_path: str, content: str) -> ParseOutcome:
    outcome = ParseOutcome(relative_path=relative_path)
    lines = content.splitlines()
    try:
        ast = javalang.parse.parse(content)
    except Exception as e:
        outcome.error = f"{type(e).__name__}: {e}"
        return outcome

    package_name = ast.package.name if ast.package else ""
    imp_map = _import_map(ast.imports)

    for tdecl in ast.types or []:
        if not isinstance(tdecl, tree.ClassDeclaration):
            continue
        class_fqn = _class_fqn(package_name, tdecl.name)
        outcome.classes.append(ExtractedClass(fqn=class_fqn, name=tdecl.name, file_rel_path=relative_path))

        methods = [m for m in (tdecl.methods or []) if isinstance(m, tree.MethodDeclaration)]
        methods.sort(key=lambda m: m.position.line if m.position else 0)
        starts = [m.position.line for m in methods if m.position]
        for idx, m in enumerate(methods):
            start = m.position.line if m.position else 1
            end = starts[idx + 1] - 1 if idx + 1 < len(starts) else len(lines)
            source = _slice_lines(lines, start, end)
            signature = _method_signature(m.name, m.parameters or [])
            mid = _method_id(class_fqn, m.name, m.parameters or [])
            invs = _collect_invocations(m.body)
            fan_out = len({i.member for i in invs if i.member})
            cc = calculate_cyclomatic_complexity(m.body, source)
            cogc = calculate_cognitive_complexity(m.body, source)
            loc = max(1, end - start + 1)
            outcome.methods.append(
                ExtractedMethod(
                    id=mid,
                    class_fqn=class_fqn,
                    name=m.name,
                    signature=signature,
                    source=source,
                    body=source,
                    line_count=loc,
                    cyclomatic_complexity=cc,
                    cognitive_complexity=cogc,
                    loc=loc,
                    fan_out=fan_out,
                )
            )
            for inv in invs:
                qualifier = inv.qualifier.strip() if isinstance(inv.qualifier, str) and inv.qualifier.strip() else None
                outcome.pending_calls.append(
                    PendingCall(
                        caller_method_id=mid,
                        caller_class_fqn=class_fqn,
                        member=inv.member,
                        qualifier=qualifier,
                        arg_count=len(inv.arguments or []),
                        import_map=imp_map,
                    )
                )
    return outcome

