import importlib.util
import os
from pathlib import Path


def _load_backend_settings():
    backend_config = Path(__file__).resolve().parents[5] / "config.py"
    spec = importlib.util.spec_from_file_location("chatui_backend_config", backend_config)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "settings", None)


_backend_settings = _load_backend_settings()

# SonarQube
SONARQUBE_URL = (
    getattr(_backend_settings, "SONARQUBE_URL", None)
    or os.getenv("SONARQUBE_URL", "http://localhost:9000")
)
SONARQUBE_TOKEN = (
    getattr(_backend_settings, "SONARQUBE_TOKEN", None)
    or os.getenv("SONARQUBE_TOKEN", "")
)

# Neo4j
NEO4J_URI = (
    getattr(_backend_settings, "NEO4J_URI", None)
    or os.getenv("NEO4J_URI", "bolt://localhost:7687")
)
NEO4J_USER = (
    getattr(_backend_settings, "NEO4J_USER", None)
    or os.getenv("NEO4J_USER", "neo4j")
)
NEO4J_PASSWORD = (
    getattr(_backend_settings, "NEO4J_PASSWORD", None)
    or os.getenv("NEO4J_PASSWORD", "password")
)

# OpenAI
OPENAI_API_KEY = (
    getattr(_backend_settings, "OPENAI_API_KEY", None)
    or getattr(_backend_settings, "OPEN_API_KEY", None)
    or os.getenv("OPENAI_API_KEY", "")
)
OPENAI_MODEL = (
    getattr(_backend_settings, "OPENAI_MODEL", None)
    or os.getenv("OPENAI_MODEL", "gpt-4o")
)
OPENAI_MAX_TOKENS = int(
    getattr(_backend_settings, "OPENAI_MAX_TOKENS", None)
    or os.getenv("OPENAI_MAX_TOKENS", "4096")
)
