from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Convert standard Postgres URLs to asyncpg protocol dynamically
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Determine database-specific connection arguments
connect_args = {}
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False

# Create the async engine
engine = create_async_engine(
    db_url,
    connect_args=connect_args,
    echo=settings.DEBUG
)

# Async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Declarative base class for models
Base = declarative_base()

# Async database session dependency inject
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
