"""Writable workspace requests for user-created experiments."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WorkspaceExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceSourceInput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1)


class WorkspaceSourcesUpdate(BaseModel):
    sources: tuple[WorkspaceSourceInput, ...] = Field(min_length=1, max_length=64)


class GraphBuildRequest(BaseModel):
    mode: Literal["source_only", "question_conditioned"] = "source_only"
    question: str | None = None

    @model_validator(mode="after")
    def validate_question(self) -> "GraphBuildRequest":
        question = self.question.strip() if self.question is not None else None

        if self.mode == "question_conditioned" and not question:
            raise ValueError("question-conditioned construction requires a question")

        self.question = question
        return self
