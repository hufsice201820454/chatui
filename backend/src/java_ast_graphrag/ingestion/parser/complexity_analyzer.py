from __future__ import annotations

from typing import Any

from javalang import tree


def _iter_children(node: Any):
    if node is None or isinstance(node, (str, int, float, bool)):
        return
    if isinstance(node, list):
        for item in node:
            yield item
        return
    if hasattr(node, "__dict__"):
        for v in vars(node).values():
            if isinstance(v, list):
                for item in v:
                    yield item
            else:
                yield v


def _count_logical_ops(source_text: str) -> int:
    n = 0
    i = 0
    while i + 1 < len(source_text):
        pair = source_text[i : i + 2]
        if pair == "&&" or pair == "||":
            n += 1
            i += 2
            continue
        i += 1
    return n


def _count_logical_chains(source_text: str) -> int:
    ops: list[str] = []
    i = 0
    while i + 1 < len(source_text):
        pair = source_text[i : i + 2]
        if pair == "&&" or pair == "||":
            ops.append(pair)
            i += 2
            continue
        i += 1
    if not ops:
        return 0
    cnt = 0
    prev = ""
    for op in ops:
        if op != prev:
            cnt += 1
            prev = op
    return cnt


def calculate_cyclomatic_complexity(method_body: Any, source_text: str) -> int:
    count = 0

    def walk(node: Any) -> None:
        nonlocal count
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, list):
            for x in node:
                walk(x)
            return

        if isinstance(
            node,
            (
                tree.IfStatement,
                tree.ForStatement,
                tree.WhileStatement,
                tree.DoStatement,
                tree.SwitchStatementCase,
                tree.CatchClause,
                tree.TernaryExpression,
            ),
        ):
            count += 1

        for c in _iter_children(node):
            walk(c)

    if method_body is not None:
        walk(method_body)
    count += _count_logical_ops(source_text or "")
    return max(1, 1 + count)


def calculate_cognitive_complexity(method_body: Any, source_text: str) -> int:
    if method_body is None:
        return 0

    score = 0

    def walk(node: Any, nesting_level: int) -> None:
        nonlocal score
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, list):
            for x in node:
                walk(x, nesting_level)
            return

        if isinstance(node, (tree.ForStatement, tree.WhileStatement, tree.DoStatement)):
            score += 1 + nesting_level
            for c in _iter_children(node):
                walk(c, nesting_level + 1)
            return

        if isinstance(node, tree.IfStatement):
            score += 1 + nesting_level
            walk(getattr(node, "condition", None), nesting_level)
            walk(getattr(node, "then_statement", None), nesting_level + 1)
            else_stmt = getattr(node, "else_statement", None)
            if else_stmt is not None:
                score += 1
                walk(else_stmt, nesting_level)
            return

        if isinstance(node, (tree.CatchClause, tree.SwitchStatement, tree.TernaryExpression)):
            score += 1
            for c in _iter_children(node):
                walk(c, nesting_level)
            return

        for c in _iter_children(node):
            walk(c, nesting_level)

    walk(method_body, 0)
    score += _count_logical_chains(source_text or "")
    return max(0, score)

