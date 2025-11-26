from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import settings
import os
import logging
import warnings
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)


def _ensure_ssl_mode(url: str) -> str:
    """
    Ensure PostgreSQL connection uses SSL in production.
    
    Adds sslmode=require if not already specified.
    
    Args:
        url: Database connection URL
        
    Returns:
        URL with SSL mode configured
    """
    if "sqlite" in url.lower():
        return url
    
    if not settings.is_production():
        return url
    
    # Parse URL
    parsed = urlparse(url)
    
    # Check if sslmode is already set
    query_params = parse_qs(parsed.query)
    
    if 'sslmode' not in query_params:
        # Add sslmode=require for production
        query_params['sslmode'] = ['require']
        
        # Reconstruct URL
        new_query = urlencode(query_params, doseq=True)
        url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        logger.info("Database SSL mode set to 'require' for production")
    
    return url


def _validate_database_url(url: str) -> None:
    """
    Validate database URL for production security requirements.
    
    Logs warnings for potential security issues.
    """
    if not settings.is_production():
        return
    
    # Check for SSL mode
    if "postgresql" in url.lower() and "sslmode" not in url.lower():
        logger.warning(
            "Production database URL missing sslmode. "
            "SSL will be automatically added (sslmode=require)."
        )
    
    # Warn about SQLite in production
    if "sqlite" in url.lower():
        warnings.warn(
            "SQLite is not recommended for production. Use PostgreSQL.",
            UserWarning
        )


def _get_database_url() -> str:
    """Prefer POSTGRES_URL if provided, fallback to settings.database_url."""
    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if pg_url:
        # Ensure async driver for SQLAlchemy
        if pg_url.startswith("postgresql://"):
            pg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if pg_url.startswith("postgres://"):
            pg_url = pg_url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        # Validate and ensure SSL
        _validate_database_url(pg_url)
        pg_url = _ensure_ssl_mode(pg_url)
        
        return pg_url
    
    # Fallback to configured URL (may be sqlite+aiosqlite)
    _validate_database_url(settings.database_url)
    return settings.database_url


def _get_engine_options() -> dict:
    """Get SQLAlchemy engine options based on database type and settings."""
    url = _get_database_url()
    
    options = {
        "echo": False,
        "pool_pre_ping": True,
    }
    
    # PostgreSQL-specific options
    if "postgresql" in url.lower():
        options.update({
            "pool_size": getattr(settings, 'pg_pool_size', 20),
            "max_overflow": getattr(settings, 'pg_pool_max_overflow', 20),
            "pool_recycle": 1800,  # 30 minutes
        })
    
    return options


# Configure async engine with pooling and heartbeat for stability under load
engine = create_async_engine(
    _get_database_url(),
    **_get_engine_options()
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
            logger.debug("Database connection verified")
        except Exception as e:
            # Connection pool pre_ping will mitigate; log at debug level
            logger.debug(f"Initial connection check failed (non-critical): {e}")

