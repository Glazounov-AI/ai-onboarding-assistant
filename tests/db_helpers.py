import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

TEST_DB_NAME = "onboarding_test"


def test_database_url() -> str:
    username = quote_plus(os.environ["POSTGRES_USER"])
    password = quote_plus(os.environ["POSTGRES_PASSWORD"])

    return (
        f"postgresql+asyncpg://{username}:{password}"
        f"@127.0.0.1:5433/{TEST_DB_NAME}"
    )


async def verified_test_engine():
    engine = create_async_engine(test_database_url())

    try:
        async with engine.connect() as connection:
            actual_database = await connection.scalar(
                text("SELECT current_database()")
            )

            if actual_database != TEST_DB_NAME:
                raise RuntimeError("Подключение не к тестовой базе")

        return engine
    except BaseException:
        await engine.dispose()
        raise