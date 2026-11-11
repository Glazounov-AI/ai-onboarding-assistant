import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.db_helpers import verified_test_engine


@pytest.fixture
async def db_session():
    engine = await verified_test_engine()

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                factory = async_sessionmaker(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                )

                async with factory() as session:
                    yield session
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()