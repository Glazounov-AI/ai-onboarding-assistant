from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import LearningSession

ACTIVE_STATUSES = (
    "waiting_for_name",
    "learning",
    "testing",
)

FINAL_STATUSES = (
    "completed",
    "cancelled",
)


class LearningSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        session_id: int,
    ) -> LearningSession | None:
        return await self.session.get(LearningSession, session_id)

    async def get_active(
        self,
        employee_id: int,
        profile_id: str,
    ) -> LearningSession | None:
        statement = select(LearningSession).where(
            LearningSession.employee_id == employee_id,
            LearningSession.profile_id == profile_id,
            LearningSession.status.in_(ACTIVE_STATUSES),
        )
        return await self.session.scalar(statement)

    async def create(
        self,
        employee_id: int,
        profile_id: str,
        profile_version: int,
    ) -> LearningSession:
        learning_session = LearningSession(
            employee_id=employee_id,
            profile_id=profile_id,
            profile_version=profile_version,
            status="learning",
        )

        self.session.add(learning_session)
        await self.session.flush()

        return learning_session

    async def change_status(
        self,
        learning_session: LearningSession,
        status: str,
    ) -> LearningSession:
        if status not in (*ACTIVE_STATUSES, *FINAL_STATUSES):
            raise ValueError(f"Недопустимый статус: {status}")

        if learning_session.status in FINAL_STATUSES:
            raise ValueError("Завершённую сессию нельзя изменять")

        learning_session.status = status

        if status in FINAL_STATUSES:
            learning_session.completed_at = datetime.now(UTC)

        await self.session.flush()
        return learning_session

    async def get_history(
        self,
        employee_id: int,
        profile_id: str,
    ) -> list[LearningSession]:
        statement = (
            select(LearningSession)
            .where(
                LearningSession.employee_id == employee_id,
                LearningSession.profile_id == profile_id,
                LearningSession.status.in_(FINAL_STATUSES),
            )
            .order_by(LearningSession.started_at.desc(), LearningSession.id.desc())
        )

        result = await self.session.scalars(statement)
        return list(result.all())