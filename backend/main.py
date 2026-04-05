"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from src.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from log_config import setup_logging
from src.core.middleware import RequestContextMiddleware
from src.datasource.sqlite.sqlite import init_db

from src.api.routes import chat, sessions, files, tools, health, models, agent_chat, java_graph

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger("chatui.main")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    _register_builtin_tools()
    _start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down")
    _stop_scheduler()
    try:
        from src.java_ast_graphrag.neo4j.client import close_neo4j_driver

        close_neo4j_driver()
    except Exception:
        pass


def _register_builtin_tools() -> None:
    """Register example built-in tools."""
    from src.tools.registry import register
    from src.tools.schemas import ToolDefinition, ToolInputSchema

    # Example: echo tool (useful for testing the tool loop)
    async def echo_handler(message: str = "") -> dict:
        return {"echo": message}

    register(
        ToolDefinition(
            name="echo",
            description="Echoes back the provided message. Useful for testing.",
            input_schema=ToolInputSchema(
                properties={"message": {"type": "string", "description": "Text to echo"}},
                required=["message"],
            ),
        ),
        handler=echo_handler,
        enabled=False,  # Disabled by default; enable via API
    )

    logger.info("Built-in tools registered")


_scheduler = None


def _start_scheduler() -> None:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from src.datasource.sqlite.sqlite import AsyncSessionLocal
    from src.utils.service import purge_expired_files

    global _scheduler

    async def _purge_job():
        async with AsyncSessionLocal() as db:
            count = await purge_expired_files(db)
            if count:
                logger.info("Scheduler: purged %d expired files", count)

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_purge_job, "interval", hours=1, id="purge_files")
    _scheduler.start()
    logger.info("Scheduler started")


def _stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ChatUI Backend – LLM chat API with tool calling, file processing, and session management",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestContextMiddleware)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health.router)
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(agent_chat.router, prefix="/api/v1")
app.include_router(java_graph.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_config=None,  # We handle logging ourselves
    )
