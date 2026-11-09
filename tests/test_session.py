import pytest

from app.core.session import (
    TrainingPhase,
    TrainingSession,
    normalize_employee_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Андрей ", "Андрей"),
        ("Иван   Петров", "Иван Петров"),
        ("Anna Smith", "Anna Smith"),
    ],
)
def test_normalize_employee_name(raw, expected):
    assert normalize_employee_name(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", " ", "A", "A" * 101, "\x00Test"],
)
def test_invalid_employee_name(raw):
    with pytest.raises(ValueError):
        normalize_employee_name(raw)


def test_training_session_defaults():
    session = TrainingSession(
        user_id=12345,
        employee_name="Андрей",
    )

    assert session.phase == TrainingPhase.LEARNING
    assert session.user_id == 12345