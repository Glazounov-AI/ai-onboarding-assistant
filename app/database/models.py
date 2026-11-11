
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True
    )
    employee_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="learning"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting_for_name', 'learning', "
            "'testing', 'completed', 'cancelled')",
            name="ck_learning_session_status",
        ),
        CheckConstraint(
            "profile_version >= 1",
            name="ck_learning_session_profile_version",
        ),
        Index(
            "uq_active_learning_session",
            "employee_id",
            "profile_id",
            unique=True,
            postgresql_where=text(
                "status IN ('waiting_for_name', 'learning', 'testing')"
            ),
        ),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    learning_session_id: Mapped[int] = mapped_column(
        ForeignKey("learning_sessions.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="in_progress"
    )
    questions_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False
    )
    score_percent: Mapped[float | None] = mapped_column()
    passed: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        UniqueConstraint(
            "learning_session_id",
            "attempt_number",
            name="uq_quiz_attempt_number",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_quiz_attempt_number",
        ),
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'cancelled')",
            name="ck_quiz_attempt_status",
        ),
        CheckConstraint(
            "score_percent IS NULL OR "
            "(score_percent >= 0 AND score_percent <= 100)",
            name="ck_quiz_attempt_score",
        ),
        Index(
            "uq_active_quiz_attempt",
            "learning_session_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
    )


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    selected_option: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "question_id",
            name="uq_quiz_answer_per_question",
        ),
        CheckConstraint(
            "selected_option BETWEEN 0 AND 3",
            name="ck_quiz_answer_option",
        ),
    )
