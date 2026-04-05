"""
Airflow 임베딩 파이프라인 전역 설정
"""
import os

# ---------------------------------------------------------------------------
# Airflow
# ---------------------------------------------------------------------------
AIRFLOW_HOME = os.getenv("AIRFLOW_HOME", "/opt/airflow")

# ---------------------------------------------------------------------------
# SQLite (ITSM 원본 DB)
# ---------------------------------------------------------------------------
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/data/itsm.db")

# ---------------------------------------------------------------------------
# AWS S3
# ---------------------------------------------------------------------------
S3_BUCKET = os.getenv("S3_BUCKET", "itsm-documents")
S3_PREFIX = os.getenv("S3_PREFIX", "docs/")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

# ---------------------------------------------------------------------------
# Embedding (OpenAI)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
EMBEDDING_MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "5"))
EMBEDDING_RETRY_MIN_WAIT = float(os.getenv("EMBEDDING_RETRY_MIN_WAIT", "1.0"))
EMBEDDING_RETRY_MAX_WAIT = float(os.getenv("EMBEDDING_RETRY_MAX_WAIT", "30.0"))

# ---------------------------------------------------------------------------
# Vision (GPT-4o)
# ---------------------------------------------------------------------------
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o")
VISION_MAX_TOKENS = int(os.getenv("VISION_MAX_TOKENS", "1024"))
VISION_PROMPT = os.getenv(
    "VISION_PROMPT",
    "이 이미지의 내용을 상세히 설명해 주세요. 표, 그래프, 텍스트 등이 있으면 모두 포함해 주세요.",
)

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))
CHROMA_COLLECTION_DICTIONARY = os.getenv("CHROMA_COLLECTION_DICTIONARY", "itsm_dictionary")
CHROMA_COLLECTION_DOCUMENT = os.getenv("CHROMA_COLLECTION_DOCUMENT", "itsm_documents")

# ---------------------------------------------------------------------------
# 파일 포맷
# ---------------------------------------------------------------------------
SUPPORTED_FORMATS = {"pdf", "docx", "xlsx", "html", "htm", "txt", "md"}
IMAGE_FORMATS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"}

# ---------------------------------------------------------------------------
# 파이프라인 실행 이력 테이블
# ---------------------------------------------------------------------------
PIPELINE_EXEC_HIS_TABLE = "PIPELINE_EXEC_HIS"
DIC_MAS_TABLE = "DIC_MAS"
DIC_DET_TABLE = "DIC_DET"

# ---------------------------------------------------------------------------
# DRM 해제 서비스
# ---------------------------------------------------------------------------
DEDRM_ENDPOINT = os.getenv("DEDRM_ENDPOINT", "http://localhost:9000/dedrm")
PDFMAKER_ENDPOINT = os.getenv("PDFMAKER_ENDPOINT", "http://localhost:9000/pdfmaker")

# ---------------------------------------------------------------------------
# 청킹
# ---------------------------------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
