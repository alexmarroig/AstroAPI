from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from schemas.synastry import SynastryPersonInput
from schemas.transits import TransitsRequest


QuestionType = Literal[
    "career",
    "relationship",
    "communication",
    "personal_growth",
    "decision_timing",
]


class CosmicDecisionRequest(TransitsRequest):
    question: str = Field(..., min_length=4, max_length=800)
    question_type: Optional[QuestionType] = None
    optional_person_chart: Optional[SynastryPersonInput] = None
    target_date: str = Field(default_factory=lambda: date.today().isoformat())


class CosmicDecisionResponse(BaseModel):
    current_cosmic_context: str
    key_influences: List[str]
    reflective_guidance: str
    suggested_reflection: str
