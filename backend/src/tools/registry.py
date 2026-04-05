"""
Tool registry (BE-TOOL-01).
Maintains an in-memory registry of available tools, their handlers, and
per-role permission sets.
"""
import logging
from typing import Any, Callable, Awaitable

from src.tools.schemas import ToolDefinition

logger = logging.getLogger("chatui.tools.registry")

# Handler type: async callable that receives **kwargs and returns any JSON-serialisable value
ToolHandler = Callable[..., Awaitable[Any]]

_tools: dict[str, ToolDefinition] = {}
_handlers: dict[str, ToolHandler] = {}
_enabled: dict[str, bool] = {}
# role → set of allowed tool names  (empty set = allow all)
_role_permissions: dict[str, set[str]] = {}


def register(
    definition: ToolDefinition,
    handler: ToolHandler,
    enabled: bool = True,
    allowed_roles: list[str] | None = None,
) -> None:
    """Register a tool with its handler."""
    name = definition.name
    _tools[name] = definition
    _handlers[name] = handler
    _enabled[name] = enabled
    if allowed_roles:
        for role in allowed_roles:
            _role_permissions.setdefault(role, set()).add(name)
    logger.info("Registered tool '%s' (enabled=%s)", name, enabled)


def get_definition(name: str) -> ToolDefinition | None:
    return _tools.get(name)


def get_handler(name: str) -> ToolHandler | None:
    return _handlers.get(name)


def list_tools(role: str | None = None, active_only: bool = True) -> list[ToolDefinition]:
    result = []
    for name, defn in _tools.items():
        if active_only and not _enabled.get(name):
            continue
        if role and role in _role_permissions:
            if name not in _role_permissions[role]:
                continue
        result.append(defn)
    return result


def set_enabled(name: str, enabled: bool) -> None:
    if name not in _tools:
        raise KeyError(f"Tool '{name}' is not registered")
    _enabled[name] = enabled
    logger.info("Tool '%s' enabled=%s", name, enabled)


def is_allowed(name: str, role: str | None = None) -> bool:
    if not _enabled.get(name):
        return False
    if role and role in _role_permissions:
        return name in _role_permissions[role]
    return True
