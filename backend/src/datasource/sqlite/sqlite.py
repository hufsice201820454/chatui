from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **({
        # timeout: busy 시 대기(초). 스트리밍으로 긴 트랜잭션이 있어도 잠금 해제까지 기다림
        "connect_args": {"check_same_thread": False, "timeout": 60.0},
        "poolclass": StaticPool,
    } if _is_sqlite else {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }),
)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """SQLite 동시 접근 완화: WAL + busy 시 밀리초 단위 대기."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
    finally:
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    개발 환경에서 테이블 자동 생성.
    운영(Oracle)에서는 DBA가 DDL 직접 실행 → DB_AUTO_CREATE=false 로 비활성화.
    """
    from config import settings
    if not getattr(settings, "DB_AUTO_CREATE", True):
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
