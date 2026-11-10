from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuizQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: int = Field(ge=0, le=3)
    source_excerpt: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_options(self) -> "QuizQuestion":
        normalized = [option.strip() for option in self.options]

        if any(not option for option in normalized):
            raise ValueError("Quiz options cannot be empty")

        if len(set(normalized)) != 4:
            raise ValueError("Quiz options must be unique")

        return self


class QuizSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    employee_id: int = Field(gt=0)
    questions: list[QuizQuestion] = Field(min_length=1)
    answers: dict[str, int] = Field(default_factory=dict)
    completed: bool = False

    @model_validator(mode="after")
    def validate_answers(self) -> "QuizSession":
        question_ids = [q.question_id for q in self.questions]

        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question IDs must be unique")

        if not set(self.answers).issubset(set(question_ids)):
            raise ValueError("Answers contain unknown question IDs")

        if any(not 0 <= answer <= 3 for answer in self.answers.values()):
            raise ValueError("Answer index must be between 0 and 3")

        if self.completed and len(self.answers) != len(self.questions):
            raise ValueError("Completed quiz must have all answers")

        return self


class QuizResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_questions: int = Field(ge=1)
    correct_answers: int = Field(ge=0)
    score_percent: float = Field(ge=0, le=100)
    passed: bool


class QuizBank(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    questions: list[QuizQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_question_ids(self) -> "QuizBank":
        ids = [question.question_id for question in self.questions]

        if len(ids) != len(set(ids)):
            raise ValueError("Quiz question IDs must be unique")

        return self
