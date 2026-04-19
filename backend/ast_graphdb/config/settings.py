import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_backend_settings():
    backend_config = Path(__file__).resolve().parents[2] / "config.py"
    spec = importlib.util.spec_from_file_location("chatui_backend_config", backend_config)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "settings", None)


_backend_settings = _load_backend_settings()


@dataclass
class Neo4jConfig:
    uri: str = (
        getattr(_backend_settings, "NEO4J_URI", None)
        or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    user: str = (
        getattr(_backend_settings, "NEO4J_USER", None)
        or os.getenv("NEO4J_USER", "neo4j")
    )
    password: str = (
        getattr(_backend_settings, "NEO4J_PASSWORD", None)
        or os.getenv("NEO4J_PASSWORD", "oky1714!@#")
    )
    database: str = (
        getattr(_backend_settings, "NEO4J_DATABASE", None)
        or os.getenv("NEO4J_DATABASE", "neo4j")
    )


@dataclass
class CollectorConfig:
    mode: str = "local"          # local | api | git
    base_path: str = (
        getattr(_backend_settings, "INGEST_BASE_PATH", None)
        or r"C:\ai_test\mes4u\src\main\java"
    )          # 로컬 디렉토리 루트 경로
    include_test: bool = False   # src/test 포함 여부
    file_encoding: str = "utf-8"


@dataclass
class IngestionConfig:
    project_id: str = (
        getattr(_backend_settings, "INGEST_PROJECT_ID", None)
        or "mes4u"
    )
    project_name: str = (
        getattr(_backend_settings, "INGEST_PROJECT_NAME", None)
        or "mes4u"
    )
    base_package: str = ""
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    batch_size: int = int(
        getattr(_backend_settings, "INGEST_BATCH_SIZE", None)
        or 500
    )
