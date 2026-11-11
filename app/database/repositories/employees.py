from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Employee


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(
        self,
        telegram_user_id: int,
    ) -> Employee | None:
        statement = select(Employee).where(
            Employee.telegram_user_id == telegram_user_id
        )
        return await self.session.scalar(statement)

    async def upsert(
        self,
        telegram_user_id: int,
        employee_name: str,
        username: str | None = None,
    ) -> Employee:
        statement = insert(Employee).values(
            telegram_user_id=telegram_user_id,
            employee_name=employee_name,
            username=username,
        )

        statement = statement.on_conflict_do_update(
            index_elements=[Employee.telegram_user_id],
            set_={
                "employee_name": statement.excluded.employee_name,
                "username": statement.excluded.username,
            },
        ).returning(Employee)

        result = await self.session.execute(
            statement,
            execution_options={"populate_existing": True},
        )
        return result.scalar_one()
