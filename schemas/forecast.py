from __future__ import annotations

from pydantic import BaseModel, Field

from .transits import TransitsRequest


class PersonalForecastRequest(TransitsRequest):
    days_ahead: int = Field(default=7, ge=1, le=30)


class PersonalForecastResponse(BaseModel):
    daily_influences: list[dict]
    weekly_themes: list[dict]
    major_cycles: list[dict]
    opportunity_windows: list[dict]
