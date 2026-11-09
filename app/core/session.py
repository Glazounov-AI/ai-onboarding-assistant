from dataclasses import dataclass
from enum import StrEnum


class TrainingPhase(StrEnum):
    WAITING_FOR_NAME = "waiting_for_name"
    LEARNING = "learning"
    TESTING = "testing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TrainingSession:
    user_id: int
    employee_name: str
    phase: TrainingPhase = TrainingPhase.LEARNING


def normalize_employee_name(value: str) -> str:
    name = " ".join(value.strip().split())

    if not 2 <= len(name) <= 100:
        raise ValueError("Имя должно содержать от 2 до 100 символов.")

    if any(ord(char) < 32 for char in name):
        raise ValueError("Имя содержит недопустимые символы.")

    return name