from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from typing import AsyncGenerator

# Create async engine
# Use echo=True for debugging SQL queries
# Pool settings can be adjusted for performance
async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    echo=False, # Set to True to see generated SQL
    # pool_size=10, # Example pool setting
    # max_overflow=20 # Example pool setting
)

# Create async session factory
# expire_on_commit=False prevents attributes from expiring after commit
AsyncSessionFactory = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False, # Consider implications based on usage
    autocommit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields an AsyncSession instance.
    Ensures the session is closed after the request.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # Optionally commit here if autocommit=False and you want commit per request
            # await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
