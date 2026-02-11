from __future__ import annotations
from typing import Optional, List, Dict, Literal, Any
from pydantic import BaseModel, Field, model_validator, AliasChoices, ConfigDict
from .common import HouseSystem, ZodiacType

class SolarReturnLocal(BaseModel):
    """Modelo para localização em revolução solar."""
    model_config = ConfigDict(populate_by_name=True)
    nome: Optional[str] = None
    lat: float = Field(..., ge=-89.9999, le=89.9999, validation_alias=AliasChoices("lat", "latitude"))
    lon: float = Field(..., ge=-180, le=180, validation_alias=AliasChoices("lon", "lng", "longitude"))
    alt_m: Optional[float] = None

class SolarReturnNatal(BaseModel):
    """Modelo para dados natais em revolução solar."""
    model_config = ConfigDict(populate_by_name=True)
    data: str = Field(..., description="Data natal no formato YYYY-MM-DD", validation_alias=AliasChoices("data", "birthDate", "birth_date"))
    hora: Optional[str] = Field(None, description="Hora natal no formato HH:MM:SS", validation_alias=AliasChoices("hora", "birthTime", "birth_time"))
    timezone: str = Field(..., description="Timezone IANA (ex.: America/Sao_Paulo)")
    local: SolarReturnLocal

class SolarReturnTarget(BaseModel):
    """Modelo para o alvo da revolução solar (ano e local)."""
    model_config = ConfigDict(populate_by_name=True)
    ano: int = Field(..., ge=1800, le=2200, validation_alias=AliasChoices("ano", "year"))
    local: SolarReturnLocal
    timezone: Optional[str] = Field(
        None, description="Timezone IANA do local alvo (ex.: America/Sao_Paulo)."
    )

class SolarReturnPreferencias(BaseModel):
    """Preferências para o cálculo da revolução solar."""
    perfil: Optional[Literal["padrao", "custom"]] = Field(
        default=None, description="Perfil de preferências (padrao/custom)."
    )
    zodiaco: ZodiacType = Field(default=ZodiacType.TROPICAL)
    ayanamsa: Optional[str] = None
    sistema_casas: HouseSystem = Field(default=HouseSystem.PLACIDUS)
    modo: Optional[Literal["geocentrico", "topocentrico"]] = Field(default="geocentrico")
    aspectos_habilitados: Optional[List[str]] = None
    orbes: Optional[Dict[str, float]] = None
    orb_max_deg: Optional[float] = Field(
        default=None, ge=0, description="Orb máximo para scoring quando em perfil custom."
    )
    janela_dias: Optional[int] = Field(
        default=None, ge=1, description="Janela em dias para busca do retorno solar."
    )
    passo_horas: Optional[int] = Field(
        default=None, ge=1, description="Passo em horas para busca do retorno solar."
    )
    max_iteracoes: Optional[int] = Field(
        default=None, ge=1, description="Iterações máximas no refinamento do retorno solar."
    )
    tolerancia_graus: Optional[float] = Field(
        default=None, gt=0, description="Tolerância em graus para refinamento do retorno solar."
    )

class SolarReturnRequest(BaseModel):
    """Modelo para requisição de cálculo de revolução solar."""
    natal: SolarReturnNatal
    alvo: SolarReturnTarget
    preferencias: Optional[SolarReturnPreferencias] = None

class SolarReturnOverlayReference(BaseModel):
    """Referência para sobreposição de revolução solar."""
    solar_return_utc: Optional[str] = Field(default=None, description="UTC ISO já calculado.")
    year: Optional[int] = Field(default=None, ge=1800, le=2200)

    @model_validator(mode="after")
    def validate_reference(self):
        if not self.solar_return_utc and not self.year:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Informe solar_return_utc ou year.")
        return self

class SolarReturnOverlayRequest(BaseModel):
    """Modelo para requisição de sobreposição de revolução solar."""
    natal: SolarReturnNatal
    alvo: SolarReturnTarget
    rs: Optional[SolarReturnOverlayReference] = None
    preferencias: Optional[SolarReturnPreferencias] = None

class SolarReturnTimelineRequest(BaseModel):
    """Modelo para requisição de timeline de revolução solar."""
    model_config = ConfigDict(populate_by_name=True)
    natal: SolarReturnNatal
    year: int = Field(..., ge=1800, le=2200, validation_alias=AliasChoices("year", "ano"))
    preferencias: Optional[SolarReturnPreferencias] = None

class SolarReturnResponse(BaseModel):
    """Resposta para o cálculo de revolução solar."""
    target_year: int
    solar_return_utc: str
    solar_return_local: str
    timezone_resolvida: Optional[str] = None
    tz_offset_minutes_usado: Optional[int] = None
    fold_usado: Optional[int] = None
    datetime_local_usado: Optional[str] = None
    datetime_utc_usado: Optional[str] = None
    avisos: Optional[List[str]] = None
    idioma: Optional[str] = None
    fonte_traducao: Optional[str] = None
