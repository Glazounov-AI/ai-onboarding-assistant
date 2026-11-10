from app.bot.handlers.onboarding import router


def test_fallback_is_registered_last():
    handlers = [
        handler.callback.__name__
        for handler in router.message.handlers
    ]

    assert handlers[-1] == "fallback"


def test_learning_handlers_precede_fallback():
    handlers = [
        handler.callback.__name__
        for handler in router.message.handlers
    ]

    assert handlers.index("answer_learning_question") < handlers.index(
        "fallback"
    )

    assert handlers.index("learning_non_text") < handlers.index(
        "fallback"
    )
