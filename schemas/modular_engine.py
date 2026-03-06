from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class ChartLocationInput(BaseModel):
    latitude: float = Field(..., ge=-89.9999, le=89.9999, validation_alias=AliasChoices("latitude", "lat"))
    longitude: float = Field(..., ge=-180.0, le=180.0, validation_alias=AliasChoices("longitude", "lng", "lon"))
    timezone: Optional[str] = Field(default=None, description="IANA timezone, ex: America/Sao_Paulo")
    tz_offset_minutes: Optional[int] = Field(default=None, ge=-840, le=840)


class ChartInput(BaseModel):
    date: str = Field(..., description="Birth date in YYYY-MM-DD format.")
    time: str = Field(..., description="Birth time in HH:MM or HH:MM:SS format.")
    latitude: Optional[float] = Field(default=None, ge=-89.9999, le=89.9999, validation_alias=AliasChoices("latitude", "lat"))
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, validation_alias=AliasChoices("longitude", "lng", "lon"))
    location: Optional[ChartLocationInput] = None
    timezone: Optional[str] = Field(default=None, description="IANA timezone, ex: America/Sao_Paulo")
    tz_offset_minutes: Optional[int] = Field(default=None, ge=-840, le=840)
    house_system: str = Field(default="P")
    zodiac_type: Literal["tropical", "sidereal"] = Field(default="tropical")
    ayanamsa: Optional[str] = None

    @model_validator(mode="after")
    def normalize_location_fields(self) -> "ChartInput":
        if self.location:
            if self.latitude is None:
                self.latitude = self.location.latitude
            if self.longitude is None:
                self.longitude = self.location.longitude
            if self.timezone is None:
                self.timezone = self.location.timezone
            if self.tz_offset_minutes is None:
                self.tz_offset_minutes = self.location.tz_offset_minutes

        if self.latitude is None or self.longitude is None:
            raise ValueError("location.latitude e location.longitude (ou latitude/longitude) são obrigatórios.")
        return self


class ChartResponse(BaseModel):
    chart_hash: str
    chart: Dict[str, Any]


class InterpretationRequest(BaseModel):
    chart_hash: Optional[str] = None
    chart_input: Optional[ChartInput] = None
    chart: Optional[Dict[str, Any]] = None
    language: str = "pt-BR"
    version: str = "v1"

    @model_validator(mode="before")
    @classmethod
    def accept_raw_chart_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "chart_input" not in data and "chart" not in data and "planets" in data:
                return {"chart": data}
        return data

    @model_validator(mode="after")
    def ensure_input(self) -> "InterpretationRequest":
        if self.chart_hash is None and self.chart_input is None and self.chart is None:
            raise ValueError("Envie chart_hash (preferencial), chart_input ou chart JSON.")
        return self


class InterpretationModuleContent(BaseModel):
    summary: str
    interpretation: str
    nuance: str
    growth: str
    questions: List[str]


class InterpretationModuleOut(BaseModel):
    id: str
    type: str
    planet: Optional[str] = None
    sign: Optional[str] = None
    house: Optional[int] = None
    aspect: Optional[str] = None
    content: InterpretationModuleContent


class InterpretationResponse(BaseModel):
    chart_hash: str
    chart: Dict[str, Any]
    modules: List[InterpretationModuleOut]
    final_interpretation: Dict[str, Any]
    method: str = "deterministic"
    cache_key: Optional[str] = None


class InterpretationRefineRequest(BaseModel):
    chart_hash: str
    language: str = "pt-BR"
    style: str = "default"
    version: str = "v1"
    force_refresh: bool = False


class InterpretationRefineResponse(BaseModel):
    chart_hash: str
    language: str
    style: str
    version: str
    refined_text: str
    source: Literal["cache", "llm", "fallback"]
    cache_key: Optional[str] = None


class PlacementInput(BaseModel):
    sign: str
    house: int


class ModuleCompositionRequest(BaseModel):
    birth_chart: Dict[str, PlacementInput]


class ModuleCompositionResponse(BaseModel):
    personality: str
    emotions: str
    relationships: str
    life_direction: str


class NarrativeRequest(BaseModel):
    birth_chart: Dict[str, Any]


class NarrativeResponse(BaseModel):
    sections: Dict[str, str]
    full_text: str
    themes: List[str]
    patterns: Dict[str, Any]


class NarrativeModuleInput(BaseModel):
    summary: str = ""
    interpretation: str = ""
    shadow: str = ""
    integration: str = ""
    questions: List[str] = Field(default_factory=list)
    theme: str = ""


class NarrativeCompositionRequest(BaseModel):
    modules: List[NarrativeModuleInput]


class NarrativeCompositionResponse(BaseModel):
    sections: Dict[str, str]
    full_text: str
