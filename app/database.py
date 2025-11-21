from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import settings
import os

def _get_database_url() -> str:
    """Prefer POSTGRES_URL if provided, fallback to settings.database_url."""
    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if pg_url:
        # Ensure async driver for SQLAlchemy
        if pg_url.startswith("postgresql://"):
            pg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if pg_url.startswith("postgres://"):
            pg_url = pg_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return pg_url
    # Fallback to configured URL (may be sqlite+aiosqlite)
    return settings.database_url


# Configure async engine with pooling and heartbeat for stability under load
# Use settings for pool size, fallback to defaults
engine = create_async_engine(
    _get_database_url(),
    echo=False,
    pool_size=getattr(settings, 'pg_pool_size', 20),
    max_overflow=getattr(settings, 'pg_pool_max_overflow', 20),
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Set a low-level heartbeat to validate connectivity
        try:
            await conn.execute(text("SELECT 1"))
        except Exception as e:
            # Connection pool pre_ping will mitigate; log at debug level
            logger.debug(f"Initial connection check failed (non-critical): {e}")

