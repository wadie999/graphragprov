"""Query planning and execution resources."""

from typing import Literal

from pydantic import BaseModel, Field


class QueryPlanRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryPlan(BaseModel):
    plan_id: str
    snapshot_id: str
    question: str
    status: Literal["query", "ambiguous", "unanswerable"]
    sparql: str | None
    rationale: str
    assumptions: tuple[str, ...]
    model: str


class QueryRunRequest(BaseModel):
    sparql: str = Field(min_length=1)
    question: str | None = None
    plan_id: str | None = None
    origin: Literal["manual", "natural_language"] = "manual"


class InteractiveQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    max_turns: int = Field(default=5, ge=1, le=10)


class ProvenanceFactor(BaseModel):
    token: str
    occurrence_id: str | None


class ProvenanceDerivation(BaseModel):
    derivation_id: str
    factors: tuple[ProvenanceFactor, ...]


class ProvenanceAnswer(BaseModel):
    binding: dict[str, object]
    polynomial: str
    derivations: tuple[ProvenanceDerivation, ...]