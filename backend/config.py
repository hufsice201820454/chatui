import logging
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent
_ENV_PATH = BACKEND_ROOT / ".env"
load_dotenv(_ENV_PATH)


def resolve_backend_path(path_str: Optional[str]) -> Optional[str]:
    """상대 경로는 backend 루트(BACKEND_ROOT) 기준으로 해석."""
    if path_str is None:
        return None
    s = str(path_str).strip()
    if not s:
        return path_str
    p = Path(s)
    if p.is_absolute():
        return str(p.resolve())
    return str((BACKEND_ROOT / p).resolve())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "ChatUI Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Database (SQLite 기본값; Oracle 연결 시 oracle+oracledb://... 로 변경)
    DATABASE_URL: str = "sqlite+aiosqlite:///./chatui.db"
    DB_AUTO_CREATE: bool = True

    # LLM (OpenAI only)
    DEFAULT_LLM_PROVIDER: str = "openai"

    # OpenAI 전용 -> 외부망 사용 전용
    OPENAI_API_KEY: Optional[str] = None  # 또는 .env 에 OPEN_API_KEY 로 설정
    OPEN_API_KEY: Optional[str] = None
    OPEN_BASE_URL: Optional[str] = None

    # 하이닉스 내부망 전용
    BASE_URL: Optional[str] = None
    API_KEY: Optional[str] = None
    VISION_BASE_URL: Optional[str] = None
    VISION_BASE_DEV_URL: Optional[str] = None
    # 내부망 Vision 전용 모델 (이미지 분석 시 사용)
    VISION_MODEL: str = "HCP-VISION-Latest"

    # OpenAI
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4096
    # 내부망 등에서 사용 가능한 모델 목록 (프론트 선택용). 비어 있으면 OPENAI_MODEL만 사용
    AVAILABLE_LLM_MODELS: List[str] = Field(default_factory=lambda: ["gpt-4o-mini", "HCP-LLM-Latest", "GLM-4.7"])
    AVAILABLE_VISION_MODELS: List[str] = Field(default_factory=lambda: ["HCP-VISION-Latest", "HCP-VISION-Latest-dev", "QWEN"])

    # Context window
    MAX_CONTEXT_TOKENS: int = 100_000
    CONTEXT_SUMMARY_THRESHOLD: float = 0.8

    # File upload
    MAX_FILE_SIZE_MB: int = 50
    UPLOAD_DIR: str = "./uploads"
    FILE_EXPIRY_DAYS: int = 7

    # SQLite MCP (ITSM 등 로컬 DB 조회용)
    SQLITE_DB_PATH: str = "./chatui_dev.db"  # 예: c:/workspace/AI/chatui_dev.db
    SQLITE_DB_TIMEOUT: float = 5.0
    # 기본 테이블명: aa_dataset_tickets_multi_lang (환경 변수 SQLITE_ITSM_TABLE 로 override 가능)
    SQLITE_ITSM_TABLE: str = "aa_dataset_tickets_multi_lang"

    # RAG / Chroma (src.rag.rag_pipeline — 필드 없으면 .env 가 무시됨)
    RAG_CHROMA_PERSIST_DIR: Optional[str] = None  # 비우면 backend/chroma (BACKEND_ROOT 기준 절대경로)
    RAG_COLLECTION_NAME: Optional[str] = None  # 인제스트 시 만든 컬렉션명과 반드시 일치
    OPENAI_EMBEDDING_MODEL: Optional[str] = None
    OPENAI_EMBEDDING_BASE_URL: Optional[str] = None

    # MCP 클라이언트 (백엔드 → MCP SSE)
    MCP_SSE_URL: Optional[str] = None

    # Java GraphRAG (Neo4j) — URI 미설정 시 그래프 조회 생략·빈 컨텍스트 (.env 권장)
    NEO4J_URI: Optional[str] = None
    NEO4J_USER: Optional[str] = None
    NEO4J_PASSWORD: Optional[str] = None
    NEO4J_DATABASE: Optional[str] = None
    # 자동 탐색 결과가 비었거나 Aura ID만 나올 때 마지막에 시도할 논리 DB (Aura 기본은 neo4j).
    NEO4J_FALLBACK_DATABASE: str = "neo4j"
    # SSL: Windows/사내망에서 SSLCertVerificationError 나면 NEO4J_SSL_RELAXED=true (+s → +ssc)
    NEO4J_SSL_USE_CERTIFI: bool = True
    NEO4J_SSL_RELAXED: bool = False
    # Neo4j 노드 라벨 (그래프 스키마에 맞게 .env 로 조정)
    NEO4J_LABEL_CLASS: str = "Class"
    NEO4J_LABEL_METHOD: str = "Method"
    NEO4J_LABEL_JAVA_FILE: str = "JavaFile"
    JAVA_GRAPHRAG_MAX_CONTEXT_TOKENS: int = 8000
    # MES Java 소스: 로컬 폴더 경로 또는 https://.../mes4u.git 원격(URL이면 캐시에 git clone).
    JAVA_MES_SOURCE_ROOT: Optional[str] = None
    # Git 원격 사용 시 clone 대상 디렉터리 (비우면 backend/.cache/java_mes_repos)
    JAVA_MES_GIT_CACHE_DIR: Optional[str] = None
    JAVA_MES_GIT_BRANCH: Optional[str] = None
    JAVA_MES_GIT_SHALLOW: bool = True

    # S3
    USE_S3: bool = False
    AWS_BUCKET_NAME: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20

    # Retry
    MAX_RETRIES: int = 3
    RETRY_MIN_WAIT: float = 1.0
    RETRY_MAX_WAIT: float = 60.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | text

    # ORACLE_PORT: int = 1521
    # ORACLE_HOST: str = None
    # ORACLE_DATABASE: str = None
    # ORACLE_SERVICE_NAME: str = None
    # ORACLE_DATABASE_USER_NAME: str = None
    # ORACLE_DATABASE_PASSWORD: str = None


settings = Settings()

_log = logging.getLogger(__name__)


def neo4j_database_for_session() -> Optional[str]:
    """`.env`/환경에서 온 논리 DB 이름만 반환. 비우면 None — `neo4j.client` 가 서버에서 DB 이름을 자동 탐색.

    `.env`에 `NEO4J_DATABASE=` 행이 있으면(비어 있어도) **파일 값을 우선**합니다.
    Windows 시스템 환경 변수 `NEO4J_DATABASE`가 잘못 잡혀 있을 때 pydantic이 덮어쓰는 문제를 막습니다.
    """
    from dotenv import dotenv_values

    if _ENV_PATH.is_file():
        vals = dotenv_values(_ENV_PATH)
        if "NEO4J_DATABASE" in vals:
            raw_file = vals.get("NEO4J_DATABASE")
            s = (raw_file or "").strip().strip('"').strip("'")
            if not s:
                return None
            # Aura 콘솔에 "Database: f4ed1c19" 처럼 유저명과 동일한 8hex 가 DB 이름인 경우가 많음 → 그대로 사용
            return s

    raw = settings.NEO4J_DATABASE
    if raw is None:
        return None
    s = str(raw).strip().strip('"').strip("'")
    if not s:
        return None
    return s
