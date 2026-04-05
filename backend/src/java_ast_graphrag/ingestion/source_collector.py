"""MES 등 Java 소스 트리에서 .java 파일 수집 (문서: SourceCollector).

기본 대상: `JAVA_MES_SOURCE_ROOT` 또는 생성자로 전달한 루트(예: mes4u 클론 경로).
실제 AST 파싱·Neo4j 적재는 별도 ingestion 파이프라인에서 이 수집 결과를 소비.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "target",
        "build",
        "out",
        "node_modules",
        ".idea",
        ".gradle",
        "__pycache__",
    }
)


@dataclass(frozen=True)
class CollectedJavaFile:
    absolute_path: Path
    relative_path: str
    content: str


class SourceCollector:
    """루트 이하 `*.java` 파일을 읽어 반환."""

    def __init__(
        self,
        root: str | Path,
        *,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> None:
        self._root = Path(root).resolve()
        self._encoding = encoding
        self._errors = errors

    @property
    def root(self) -> Path:
        return self._root

    def iter_java_files(self) -> Iterator[CollectedJavaFile]:
        if not self._root.is_dir():
            raise FileNotFoundError(f"Java source root is not a directory: {self._root}")

        for path in sorted(self._root.rglob("*.java")):
            if any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            rel = path.relative_to(self._root).as_posix()
            try:
                text = path.read_text(encoding=self._encoding, errors=self._errors)
            except OSError:
                continue
            yield CollectedJavaFile(
                absolute_path=path,
                relative_path=rel,
                content=text,
            )

    def collect(self) -> list[CollectedJavaFile]:
        return list(self.iter_java_files())


def source_collector_from_settings() -> SourceCollector | None:
    """`JAVA_MES_SOURCE_ROOT`가 있으면 `SourceCollector`, 없으면 None.

    값이 `https://...git` 같은 원격이면 캐시에 clone 후 그 경로를 사용합니다.
    """
    from config import settings

    from src.java_ast_graphrag.ingestion.git_workspace import resolve_java_mes_root

    raw = getattr(settings, "JAVA_MES_SOURCE_ROOT", None)
    if not raw or not str(raw).strip():
        return None
    return SourceCollector(resolve_java_mes_root(str(raw).strip()))
