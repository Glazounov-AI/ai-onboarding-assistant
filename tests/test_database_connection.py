from sqlalchemy import text

from tests.db_helpers import verified_test_engine


async def test_connection_to_test_database():
    engine = await verified_test_engine()

    try:
        async with engine.connect() as connection:
            database_name = await connection.scalar(
                text("SELECT current_database()")
            )
            assert database_name == "onboarding_test"
    finally:
        await engine.dispose()