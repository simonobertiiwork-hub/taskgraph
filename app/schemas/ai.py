from pydantic import BaseModel, Field, model_validator


class AISubtask(BaseModel):
    local_id: str = Field(
        min_length=1,
        max_length=50,
        description="Локальный идентификатор подзадачи внутри AI-ответа",
    )
    title: str = Field(
        min_length=1,
        max_length=300,
    )
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "AISubtask":
        if self.local_id in self.depends_on:
            raise ValueError("Подзадача не может зависеть сама от себя")

        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("Список depends_on содержит дубликаты")

        return self


class AIDecompositionResult(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=1000,
    )
    subtasks: list[AISubtask] = Field(
        min_length=1,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_subtasks(self) -> "AIDecompositionResult":
        local_ids = [subtask.local_id for subtask in self.subtasks]

        if len(local_ids) != len(set(local_ids)):
            raise ValueError(
                "local_id должен быть уникальным для каждой подзадачи"
            )

        known_ids = set(local_ids)

        for subtask in self.subtasks:
            unknown_dependencies = (
                set(subtask.depends_on) - known_ids
            )

            if unknown_dependencies:
                unknown = ", ".join(sorted(unknown_dependencies))
                raise ValueError(
                    f"Неизвестные зависимости: {unknown}"
                )

        return self