from __future__ import annotations

from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SolarReturnDados(BaseModel):
    ano: int = Field(..., description="Ano em que o evento ocorreu.")
    mes: int = Field(..., description="Mês em que o evento ocorreu.")
    dia: int = Field(..., description="Dia em que o evento ocorreu.")
    hora: int = Field(..., description="Hora em que o evento ocorreu.")
    minuto: int = Field(0, description="Minuto em que o evento ocorreu.")
    segundo: int = Field(0, description="Segundo em que o evento ocorreu.")
    lat: float = Field(..., description="Latitude do local (em graus).")
    lon: float = Field(..., description="Longitude do local (em graus).")
    timezone: str = Field(..., description="Timezone IANA (ex.: America/Sao_Paulo).")

    @field_validator("lat")
    @classmethod
    def validar_lat(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude deve estar entre -90 e 90 graus.")
        return value

    @field_validator("lon")
    @classmethod
    def validar_lon(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude deve estar entre -180 e 180 graus.")
        return value

    @field_validator("timezone")
    @classmethod
    def validar_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone IANA inválido. Use um identificador como America/Sao_Paulo.") from exc
        return value


class SolarReturnPreferencias(BaseModel):
    model_config = ConfigDict(extra="allow")

    sistema_casas: Optional[str] = Field(
        default=None,
        description="Sistema de casas astrológicas (ex.: P, K, R).",
    )
    tipo_zodiaco: Optional[str] = Field(
        default=None,
        description="Tipo de zodíaco (ex.: tropical, sideral).",
    )
    ayanamsa: Optional[str] = Field(
        default=None,
        description="Ayanamsa para zodíaco sideral (ex.: lahiri).",
    )
    aspectos_habilitados: Optional[List[str]] = Field(
        default=None,
        description="Lista de aspectos habilitados (ex.: ['conj', 'opos', 'quad', 'tri', 'sext']).",
    )
    orbes: Optional[Dict[str, float]] = Field(
        default=None,
        description="Orbes por aspecto, ex.: {'conj': 8, 'opos': 6}.",
    )
    timezone_estrito: bool = Field(
        default=False,
        description="Quando true, rejeita horários ambíguos em transições de DST.",
    )
    janela_dias: Optional[int] = Field(
        default=None,
        description="Janela em dias para busca do retorno solar.",
        ge=1,
    )
    passo_horas: Optional[int] = Field(
        default=None,
        description="Passo em horas para busca do retorno solar.",
        ge=1,
    )
    max_iteracoes: Optional[int] = Field(
        default=None,
        description="Iterações máximas no refinamento do retorno solar.",
        ge=1,
    )
    tolerancia_graus: Optional[float] = Field(
        default=None,
        description="Tolerância em graus para refinamento do retorno solar.",
        gt=0,
    aspectos_habilitados: Optional[List[str]] = Field(
        default=None,
        description="Lista de aspectos habilitados (ex.: conjunction, square).",
    )
    orbes: Optional[Dict[str, float]] = Field(
        default=None,
        description="Orbes personalizados por aspecto (ex.: {'conjunction': 5}).",
    )


class SolarReturnRequest(BaseModel):
    natal: SolarReturnDados = Field(..., description="Dados natais para o retorno solar.")
    alvo: SolarReturnDados = Field(..., description="Dados do alvo para o retorno solar.")
    preferencias: Optional[SolarReturnPreferencias] = Field(
        default=None,
        description="Preferências de cálculo do retorno solar.",
    )


class SolarReturnResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    metadados_tecnicos: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadados técnicos adicionais do cálculo.",
    )
    avisos: Optional[List[str]] = Field(
        default=None,
        description="Lista de avisos relevantes para o retorno solar.",
    )
    interpretacao: Optional[str] = Field(
        default=None,
        description="Interpretação textual do retorno solar.",
    )
