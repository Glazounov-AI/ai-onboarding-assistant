
import os
from collections.abc import AsyncIterator
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

load_dotenv()


def build_database_url() -> str:
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5433")
    database = os.environ["POSTGRES_DB"]
    username = quote_plus(os.environ["POSTGRES_USER"])
    password = quote_plus(os.environ["POSTGRES_PASSWORD"])

    return (
        f"postgresql+asyncpg://{username}:{password}"
        f"@{host}:{port}/{database}"
    )


engine = create_async_engine(
    build_database_url(),
    echo=False,
    pool_pre_ping=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
