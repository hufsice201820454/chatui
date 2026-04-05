"""적재 파이프라인 내부 모델."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedClass:
    fqn: str
    name: str
    extends: str
    implements: str
    depends_on: str
    file_rel_path: str


@dataclass
class ExtractedMethod:
    id: str
    class_fqn: str
    name: str
    signature: str
    source: str
    line_count: int
    fan_out: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    param_count: int


@dataclass
class ExtractedCall:
    caller_method_id: str
    callee_method_id: str


@dataclass
class PendingCall:
    caller_method_id: str
    member: str
    qualifier: str | None
    arg_count: int
    caller_class_fqn: str
    import_map: dict[str, str] = field(default_factory=dict)


@dataclass
class FileParseOutcome:
    relative_path: str
    import_map: dict[str, str] = field(default_factory=dict)
    classes: list[ExtractedClass] = field(default_factory=list)
    methods: list[ExtractedMethod] = field(default_factory=list)
    calls: list[ExtractedCall] = field(default_factory=list)
    pending_calls: list[PendingCall] = field(default_factory=list)
    error: str | None = None


@dataclass
class WorkspaceGraph:
    files: list[FileParseOutcome] = field(default_factory=list)

    def all_classes(self) -> list[ExtractedClass]:
        return [c for f in self.files for c in f.classes]

    def all_methods(self) -> list[ExtractedMethod]:
        return [m for f in self.files for m in f.methods]

    def all_calls(self) -> list[ExtractedCall]:
        return [x for f in self.files for x in f.calls]


@dataclass
class IngestionReport:
    dry_run: bool
    root: str
    files_seen: int
    files_parsed_ok: int
    files_failed: int
    classes_upserted: int
    methods_upserted: int
    calls_merged: int
    errors: list[str] = field(default_factory=list)
