from app.core.settings import Settings


def test_default_settings(monkeypatch):
    for key in (
        "BOT_TOKEN",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.postgres_host == "db"
    assert settings.postgres_port == 5432
    assert settings.training_profile.endswith(".yaml")


def test_missing_secrets(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    settings = Settings(_env_file=None)

    try:
        settings.validate_runtime()
    except ValueError as exc:
        assert "BOT_TOKEN" in str(exc)
    else:
        raise AssertionError("Expected validation error")