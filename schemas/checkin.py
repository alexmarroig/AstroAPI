from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


CheckinState = Literal[
    "inspired",
    "focused",
    "restless",
    "social",
    "reflective",
    "low_energy",
]


class CheckinSubmitRequest(BaseModel):
    state: CheckinState = Field(..., description="Estado atual selecionado pelo usuario.")


class CheckinEntry(BaseModel):
    date: str
    state: CheckinState
    moon_sign: str
    moon_house: int
    transit_summary: str


class CheckinPattern(BaseModel):
    pattern: str
    observation: str


class CheckinSubmitResponse(BaseModel):
    entry: CheckinEntry
    cosmic_context: str
    pattern: Optional[CheckinPattern] = None


class CheckinHistoryResponse(BaseModel):
    entries: List[CheckinEntry]
    pattern: Optional[CheckinPattern] = None
