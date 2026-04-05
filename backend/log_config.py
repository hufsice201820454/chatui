import json
import logging
import logging.handlers
import os
import sys
from typing import Any

from config import BACKEND_ROOT, settings

LOG_DIR = str(BACKEND_ROOT / "logs")


class JsonFormatter(logging.Formatter):
    """JSON structured log formatter (stdout)."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "user_id", "session_id", "duration_ms", "tool_name"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Plain text formatter for log files."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} [{record.levelname}] {record.name}: {record.getMessage()}"
        for key in ("request_id", "session_id", "duration_ms", "tool_name"):
            if hasattr(record, key):
                base += f" | {key}={getattr(record, key)}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # ── stdout 핸들러 ──────────────────────────────────────────────────────
    # Windows cp949 콘솔에서 한글/유니코드 문자(—, ✓ 등) 인코딩 오류 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass
    stdout_handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT == "json":
        stdout_handler.setFormatter(JsonFormatter())
    else:
        stdout_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    handlers: list[logging.Handler] = [stdout_handler]

    # ── 파일 핸들러 (logs/app_YYYY-MM-DD.txt) ─────────────────────────────
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "app.txt"),
        when="midnight",
        interval=1,
        backupCount=30,         # 30일 보관
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(TextFormatter())
    handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = handlers

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
