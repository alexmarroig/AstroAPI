from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class SynastryPersonInput(BaseModel):
    name: Optional[str] = None

    # Birth date/time (preferred contract)
    birth_date: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_date", "birthDate"),
    )
    birth_time: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("birth_time", "birthTime"),
    )

    # Legacy numeric natal fields
    natal_year: Optional[int] = Field(default=None, ge=1800, le=2200)
    natal_month: Optional[int] = Field(default=None, ge=1, le=12)
    natal_day: Optional[int] = Field(default=None, ge=1, le=31)
    natal_hour: Optional[int] = Field(default=None, ge=0, le=23)
    natal_minute: int = Field(default=0, ge=0, le=59)
    natal_second: int = Field(default=0, ge=0, le=59)

    # Geo/timezone
    lat: float = Field(..., ge=-89.9999, le=89.9999, validation_alias=AliasChoices("lat", "latitude"))
    lng: float = Field(..., ge=-180, le=180, validation_alias=AliasChoices("lng", "longitude", "lon"))
    timezone: Optional[str] = Field(default=None)
    tz_offset_minutes: Optional[int] = Field(default=None, ge=-840, le=840)

    # Chart preferences
    house_system: str = Field(default="P")
    zodiac_type: str = Field(default="tropical")
    ayanamsa: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_birth_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # year/month/day aliases
        if "year" in data and "natal_year" not in data:
            data["natal_year"] = data.get("year")
        if "month" in data and "natal_month" not in data:
            data["natal_month"] = data.get("month")
        if "day" in data and "natal_day" not in data:
            data["natal_day"] = data.get("day")
        if "hour" in data and "natal_hour" not in data:
            data["natal_hour"] = data.get("hour")
        if "minute" in data and "natal_minute" not in data:
            data["natal_minute"] = data.get("minute")
        if "second" in data and "natal_second" not in data:
            data["natal_second"] = data.get("second")

        # Convert numeric natal fields into birth_date/birth_time when absent
        if (
            not data.get("birth_date")
            and data.get("natal_year")
            and data.get("natal_month")
            and data.get("natal_day")
        ):
            data["birth_date"] = f"{int(data['natal_year']):04d}-{int(data['natal_month']):02d}-{int(data['natal_day']):02d}"

        if not data.get("birth_time"):
            hour = int(data.get("natal_hour") or 12)
            minute = int(data.get("natal_minute") or 0)
            second = int(data.get("natal_second") or 0)
            data["birth_time"] = f"{hour:02d}:{minute:02d}:{second:02d}"

        return data

    @model_validator(mode="after")
    def validate_birth(self) -> "SynastryPersonInput":
        if not self.birth_date:
            raise ValueError("birth_date é obrigatório.")
        # Validate format
        datetime.strptime(self.birth_date, "%Y-%m-%d")
        if self.birth_time:
            # Accept HH:MM and HH:MM:SS
            if len(self.birth_time.split(":")) == 2:
                datetime.strptime(self.birth_time, "%H:%M")
            else:
                datetime.strptime(self.birth_time, "%H:%M:%S")
        return self


class SynastryCompareRequest(BaseModel):
    # Unified contract supports both new and legacy keys
    person_a: Optional[SynastryPersonInput] = Field(default=None, validation_alias=AliasChoices("person_a", "personA"))
    person_b: Optional[SynastryPersonInput] = Field(default=None, validation_alias=AliasChoices("person_b", "personB"))
    person1: Optional[SynastryPersonInput] = None
    person2: Optional[SynastryPersonInput] = None

    @model_validator(mode="after")
    def resolve_pairs(self) -> "SynastryCompareRequest":
        if self.person_a is None and self.person1 is not None:
            self.person_a = self.person1
        if self.person_b is None and self.person2 is not None:
            self.person_b = self.person2
        if self.person_a is None or self.person_b is None:
            raise ValueError("Envie person_a/person_b ou person1/person2.")
        return self


class SynastryAspectOut(BaseModel):
    person1_planet: str
    person2_planet: str
    aspect_type: str
    orb: float
    category: str
    interpretation: str


class SynastryHouseOverlayOut(BaseModel):
    title: str
    text: str


class SynastryCompareResponse(BaseModel):
    overview: str
    summary: str
    emotional_dynamic: str
    communication_dynamic: str
    attraction_dynamic: str
    strengths: List[str]
    growth_areas: List[str]
    aspects: List[SynastryAspectOut]
    house_overlays: List[SynastryHouseOverlayOut]
    relationship_overview: Optional[str] = None
    key_aspects: Optional[List[SynastryAspectOut]] = None
    # Backward-compatible raw charts for advanced UIs
    person_a: Optional[Dict[str, Any]] = None
    person_b: Optional[Dict[str, Any]] = None
