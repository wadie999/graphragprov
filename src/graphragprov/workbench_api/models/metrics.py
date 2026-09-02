"""Extensible metric resources."""

from pydantic import BaseModel

MetricValue = int | float | bool | str


class MetricObservation(BaseModel):
    key: str
    label: str
    scope: str
    value: MetricValue
    unit: str | None = None
    target_id: str | None = None
    method: str | None = None


class MetricCollection(BaseModel):
    items: tuple[MetricObservation, ...]
