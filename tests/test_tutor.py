
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIConnectionError

from app.services.tutor import TutorError, TutorService


@pytest.fixture
def client():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client


@pytest.fixture
def tutor(client):
    return TutorService(
        client=client,
        model="gpt-4o-mini",
        material="Все заявки регистрируются в трекере.",
        system_prompt="Отвечай только по учебному материалу.",
    )


@pytest.mark.asyncio
async def test_answer_success(tutor, client):
    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content="В трекере."))
    ]
    client.chat.completions.create.return_value = response

    answer = await tutor.answer("Где регистрировать заявки?")

    assert answer == "В трекере."
    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_question(tutor):
    with pytest.raises(ValueError, match="empty"):
        await tutor.answer("   ")


@pytest.mark.asyncio
async def test_question_too_long(tutor):
    with pytest.raises(ValueError, match="too long"):
        await tutor.answer("А" * 2001)


def test_empty_material(client):
    with pytest.raises(ValueError, match="cannot be empty"):
        TutorService(
            client=client,
            model="gpt-4o-mini",
            material=" ",
            system_prompt="Отвечай только по учебному материалу.",
        )


@pytest.mark.asyncio
async def test_empty_api_response(tutor, client):
    response = MagicMock()
    response.choices = []
    client.chat.completions.create.return_value = response

    with pytest.raises(TutorError, match="no choices"):
        await tutor.answer("Вопрос")


@pytest.mark.asyncio
async def test_api_connection_error(tutor, client):
    client.chat.completions.create.side_effect = APIConnectionError(
        request=MagicMock()
    )

    with pytest.raises(TutorError, match="temporarily unavailable"):
        await tutor.answer("Вопрос")


