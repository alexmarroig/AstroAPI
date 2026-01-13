from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ValidateLocalDatetimeRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM or HH:MM:SS")
    timezone: str = Field(..., description="Timezone IANA (ex.: America/Sao_Paulo).")
    strict: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos ou inexistentes.",
    )
    prefer_fold: bool = Field(
        default=False,
        description="Quando true, usa fold=1 em horários ambíguos.",
    )


class ValidateLocalDatetimeResponse(BaseModel):
    ok: bool
    local_datetime: str
    utc_datetime: str
    tz_offset_minutes: int
    is_ambiguous: bool
    is_nonexistent: bool
    fold_used: int
    warnings: List[str]
