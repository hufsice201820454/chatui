"""javalang 기반 Java 소스 → 추출 모델 (파일 단위)."""
from __future__ import annotations

import logging
import re
from typing import Any

import javalang
from javalang import tree
from javalang.parser import JavaSyntaxError

from src.java_ast_graphrag.graphrag.ingestion_pipeline.models import (
    ExtractedClass,
    ExtractedMethod,
    FileParseOutcome,
    PendingCall,
)

logger = logging.getLogger(__name__)


def _sanitize_for_javalang(source: str) -> str:
    """javalang이 파싱 못 하는 문법 완화.

    예: 캐스트에 붙는 타입 사용 어노테이션 `(@NotBlank String)` → `(String)`.
    """
    pattern = re.compile(r"\(\s*@[A-Za-z_][\w.]*\s+")
    while True:
        new = pattern.sub("(", source)
        if new == source:
            return new
        source = new


def _ref_type_str(rt: tree.ReferenceType | None) -> str:
    if rt is None:
        return ""
    parts: list[str] = []
    cur: tree.ReferenceType | None = rt
    while cur is not None:
        parts.append(cur.name)
        cur = cur.sub_type
    s = ".".join(parts)
    dims = getattr(rt, "dimensions", None) or []
    return s + ("[]" * len(dims)) if dims else s


def _type_to_string(t: Any) -> str:
    if t is None:
        return "void"
    if isinstance(t, tree.BasicType):
        dims = getattr(t, "dimensions", None) or []
        return t.name + "[]" * len(dims)
    if isinstance(t, tree.ReferenceType):
        return _ref_type_str(t)
    return "var"


def _build_import_map(imports: list[tree.Import]) -> dict[str, str]:
    out: dict[str, str] = {}
    for imp in imports or []:
        if getattr(imp, "wildcard", False):
            continue
        path = imp.path
        if not path:
            continue
        simple = path.rsplit(".", 1)[-1]
        out[simple] = path
    return out


def _depends_on_from_imports(imports: list[tree.Import]) -> str:
    paths: list[str] = []
    for imp in imports or []:
        if getattr(imp, "wildcard", False):
            continue
        if imp.path:
            paths.append(imp.path)
    return ";".join(sorted(set(paths)))


def _class_fqn(package: str, outer: list[str], name: str) -> str:
    tail = ".".join(outer + [name]) if outer else name
    return f"{package}.{tail}" if package else tail


def _estimate_cc(text: str) -> int:
    if not text.strip():
        return 1
    n = len(
        re.findall(
            r"\b(if|while|for|catch|case)\b|&&|\|\||\?",
            text,
        )
    )
    return max(1, 1 + n)


def _method_signature_string(name: str, parameters: list) -> str:
    pts = [_type_to_string(getattr(p, "type", None)) for p in parameters or []]
    return f"{name}({', '.join(pts)})"


def _method_id(class_fqn: str, name: str, parameters: list) -> str:
    return f"{class_fqn}#{_method_signature_string(name, parameters)}"


def _slice_method_lines(lines: list[str], start_line: int, end_line: int) -> str:
    if start_line < 1:
        start_line = 1
    i0 = start_line - 1
    i1 = min(len(lines), max(i0 + 1, end_line))
    return "\n".join(lines[i0:i1])


def _collect_invocations(body: Any) -> list[tree.MethodInvocation]:
    if body is None:
        return []
    found: list[tree.MethodInvocation] = []

    def walk(node: Any) -> None:
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, tree.MethodInvocation):
            found.append(node)
        if isinstance(node, list):
            for x in node:
                walk(x)
            return
        if hasattr(node, "__dict__"):
            for v in vars(node).values():
                walk(v)

    walk(body)
    return found


def _walk_type_declaration(
    type_decl: tree.ClassDeclaration | tree.InterfaceDeclaration,
    *,
    package: str,
    outer: list[str],
    lines: list[str],
    file_rel: str,
    import_map: dict[str, str],
    depends_on: str,
    classes: list[ExtractedClass],
    methods: list[ExtractedMethod],
    pending: list[PendingCall],
) -> None:
    fqn = _class_fqn(package, outer, type_decl.name)
    extends_s = ""
    impls = ""
    if isinstance(type_decl, tree.ClassDeclaration):
        if type_decl.extends:
            extends_s = _ref_type_str(type_decl.extends)
        if type_decl.implements:
            impls = ",".join(_ref_type_str(x) for x in type_decl.implements)
    elif isinstance(type_decl, tree.InterfaceDeclaration):
        # javalang: 인터페이스의 superinterface 목록은 `extends`에 리스트로 옴 (`implements` 속성 없음)
        ext = type_decl.extends
        if ext:
            if isinstance(ext, list):
                extends_s = ",".join(_ref_type_str(x) for x in ext)
            else:
                extends_s = _ref_type_str(ext)

    classes.append(
        ExtractedClass(
            fqn=fqn,
            name=type_decl.name,
            extends=extends_s,
            implements=impls,
            depends_on=depends_on,
            file_rel_path=file_rel,
        )
    )

    body_decls = list(type_decl.body or [])
    method_decls: list[tree.MethodDeclaration] = []
    nested: list[tree.ClassDeclaration | tree.InterfaceDeclaration] = []
    for d in body_decls:
        if isinstance(d, (tree.ClassDeclaration, tree.InterfaceDeclaration)):
            nested.append(d)
        elif isinstance(d, tree.MethodDeclaration):
            method_decls.append(d)

    method_decls.sort(
        key=lambda m: m.position.line if m.position else 0,
    )
    next_lines = [m.position.line for m in method_decls if m.position]
    for idx, m in enumerate(method_decls):
        start = m.position.line if m.position else 1
        if idx + 1 < len(next_lines):
            end = next_lines[idx + 1] - 1
        else:
            end = len(lines)
        src = _slice_method_lines(lines, start, end)
        sig = _method_signature_string(m.name, m.parameters)
        mid = _method_id(fqn, m.name, m.parameters)
        invs = _collect_invocations(m.body) if m.body else []
        fan_out = len({i.member for i in invs if i.member})
        cc = _estimate_cc(src)
        methods.append(
            ExtractedMethod(
                id=mid,
                class_fqn=fqn,
                name=m.name,
                signature=sig,
                source=src,
                line_count=max(1, end - start + 1),
                fan_out=fan_out,
                cyclomatic_complexity=cc,
                cognitive_complexity=cc,
                param_count=len(m.parameters or []),
            )
        )
        for inv in invs:
            qual = inv.qualifier
            if isinstance(qual, str):
                q = qual.strip() or None
            else:
                q = None
            pending.append(
                PendingCall(
                    caller_method_id=mid,
                    member=inv.member,
                    qualifier=q,
                    arg_count=len(inv.arguments or []),
                    caller_class_fqn=fqn,
                    import_map=import_map,
                )
            )

    for child in nested:
        _walk_type_declaration(
            child,
            package=package,
            outer=outer + [type_decl.name],
            lines=lines,
            file_rel=file_rel,
            import_map=import_map,
            depends_on=depends_on,
            classes=classes,
            methods=methods,
            pending=pending,
        )


def parse_java_file(relative_path: str, content: str) -> FileParseOutcome:
    outcome = FileParseOutcome(relative_path=relative_path)
    content = _sanitize_for_javalang(content)
    try:
        ast = javalang.parse.parse(content)
    except JavaSyntaxError as e:
        outcome.error = f"JavaSyntaxError: {e}"
        logger.debug("parse skip %s: %s", relative_path, e)
        return outcome
    except Exception as e:
        outcome.error = f"{type(e).__name__}: {e}"
        logger.warning("parse failed %s: %s", relative_path, e)
        return outcome

    package = ast.package.name if ast.package else ""
    lines = content.splitlines()
    import_map = _build_import_map(ast.imports)
    outcome.import_map = dict(import_map)
    depends = _depends_on_from_imports(ast.imports)

    pending: list[PendingCall] = []
    for tdecl in ast.types or []:
        if isinstance(tdecl, (tree.ClassDeclaration, tree.InterfaceDeclaration)):
            _walk_type_declaration(
                tdecl,
                package=package,
                outer=[],
                lines=lines,
                file_rel=relative_path,
                import_map=import_map,
                depends_on=depends,
                classes=outcome.classes,
                methods=outcome.methods,
                pending=pending,
            )
        # EnumDeclaration 등은 스킵

    outcome.pending_calls = pending
    return outcome
