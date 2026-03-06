from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from astro.aspects import compute_transit_aspects, get_aspects_profile
from astro.ephemeris import compute_chart, compute_transits
from astro.i18n_ptbr import aspect_to_ptbr, planet_key_to_ptbr
from schemas.synastry import (
    SynastryAspectOut,
    SynastryCompareRequest,
    SynastryCompareResponse,
    SynastryHouseOverlayOut,
)
from services.astro_logic import get_house_for_lon
from services.relationship_cycles import detect_relationship_evolution
from services.time_utils import get_tz_offset_minutes, parse_local_datetime_ptbr

from .common import get_auth

router = APIRouter()


def _normalize_time(time_str: str | None) -> str:
    if not time_str:
        return "12:00:00"
    if len(time_str.split(":")) == 2:
        return f"{time_str}:00"
    return time_str


def _build_person_chart(person: Any, request: Request) -> Dict[str, Any]:
    birth_time = _normalize_time(person.birth_time)
    local_dt, warnings, time_missing = parse_local_datetime_ptbr(person.birth_date, birth_time)
    tz_offset = get_tz_offset_minutes(
        local_dt,
        person.timezone,
        person.tz_offset_minutes,
        request_id=getattr(request.state, "request_id", None),
    )

    chart = compute_chart(
        year=local_dt.year,
        month=local_dt.month,
        day=local_dt.day,
        hour=local_dt.hour,
        minute=local_dt.minute,
        second=local_dt.second,
        lat=person.lat,
        lng=person.lng,
        tz_offset_minutes=tz_offset,
        house_system=person.house_system,
        zodiac_type=person.zodiac_type,
        ayanamsa=person.ayanamsa,
    )

    return {
        "name": person.name or "Pessoa",
        "birth_date": person.birth_date,
        "birth_time": birth_time,
        "birth_time_precise": not time_missing,
        "timezone": person.timezone,
        "tz_offset_minutes": tz_offset,
        "warnings": warnings,
        "chart": chart,
    }


def _aspect_to_out(item: Dict[str, Any]) -> SynastryAspectOut:
    influence = str(item.get("influence", "")).lower()
    category = "strength" if influence in {"supportive", "subtle", "adjusting"} else "growth"
    p1 = str(item.get("transit_planet", ""))
    p2 = str(item.get("natal_planet", ""))
    asp = str(item.get("aspect", ""))
    orb = float(item.get("orb", 0.0))
    return SynastryAspectOut(
        person1_planet=planet_key_to_ptbr(p1),
        person2_planet=planet_key_to_ptbr(p2),
        aspect_type=aspect_to_ptbr(asp),
        orb=round(abs(orb), 3),
        category=category,
        interpretation=(
            f"{planet_key_to_ptbr(p1)} em {aspect_to_ptbr(asp)} com {planet_key_to_ptbr(p2)} "
            f"ativa aprendizados mútuos com intensidade de orb {round(abs(orb), 2)}°."
        ),
    )


def _house_overlays(person_a: Dict[str, Any], person_b: Dict[str, Any]) -> List[SynastryHouseOverlayOut]:
    overlays: List[SynastryHouseOverlayOut] = []
    houses_a = person_a["chart"].get("houses", {}).get("cusps", [])
    houses_b = person_b["chart"].get("houses", {}).get("cusps", [])
    planets_a = person_a["chart"].get("planets", {})
    planets_b = person_b["chart"].get("planets", {})

    for name, data in list(planets_b.items())[:8]:
        lon = float(data.get("lon", 0.0))
        house = get_house_for_lon(houses_a, lon)
        overlays.append(
            SynastryHouseOverlayOut(
                title=f"{person_b['name']}: {planet_key_to_ptbr(name)} na Casa {house} de {person_a['name']}",
                text=f"Pode ativar temas da Casa {house} em {person_a['name']}, trazendo foco relacional nessa área.",
            )
        )

    for name, data in list(planets_a.items())[:8]:
        lon = float(data.get("lon", 0.0))
        house = get_house_for_lon(houses_b, lon)
        overlays.append(
            SynastryHouseOverlayOut(
                title=f"{person_a['name']}: {planet_key_to_ptbr(name)} na Casa {house} de {person_b['name']}",
                text=f"Indica como {person_a['name']} costuma impactar a Casa {house} de {person_b['name']}.",
            )
        )
    return overlays[:10]


def _build_compare_payload(person_a: Dict[str, Any], person_b: Dict[str, Any]) -> SynastryCompareResponse:
    _, aspects_profile = get_aspects_profile()
    raw_aspects = compute_transit_aspects(
        transit_planets=person_b["chart"].get("planets", {}),
        natal_planets=person_a["chart"].get("planets", {}),
        aspects=aspects_profile,
    )
    all_aspects = [_aspect_to_out(a) for a in raw_aspects]
    strength_aspects = [a for a in all_aspects if a.category == "strength"][:12]
    growth_aspects = [a for a in all_aspects if a.category == "growth"][:12]
    strengths = [a.interpretation for a in strength_aspects[:6]]
    growth = [a.interpretation for a in growth_aspects[:6]]

    return SynastryCompareResponse(
        overview="Compatibilidade dinâmica com pontos de fluidez e crescimento.",
        summary="Leitura geral de compatibilidade baseada em aspectos e sobreposição de casas.",
        emotional_dynamic="A dinâmica emocional mostra como cada pessoa acolhe e responde ao outro no dia a dia.",
        communication_dynamic="A comunicação tende a refletir padrões de escuta, timing e clareza entre vocês.",
        attraction_dynamic="A atração surge da combinação entre desejo, afeto e segurança emocional.",
        strengths=strengths,
        growth_areas=growth,
        aspects=all_aspects[:20],
        relationship_overview="Compatibilidade dinÃ¢mica com pontos de fluidez e crescimento.",
        key_aspects=all_aspects[:10],
        house_overlays=_house_overlays(person_a, person_b),
        person_a=person_a,
        person_b=person_b,
    )


@router.post("/v1/synastry/compare", response_model=SynastryCompareResponse)
async def synastry_compare(body: SynastryCompareRequest, request: Request, auth=Depends(get_auth)):
    try:
        person_a = _build_person_chart(body.person_a, request)
        person_b = _build_person_chart(body.person_b, request)
        return _build_compare_payload(person_a, person_b)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Falha ao calcular sinastria: {exc}") from exc


@router.post("/v1/synastry/deep")
async def synastry_deep(body: SynastryCompareRequest, request: Request, auth=Depends(get_auth)):
    person_a = _build_person_chart(body.person_a, request)
    person_b = _build_person_chart(body.person_b, request)
    base = _build_compare_payload(person_a, person_b)
    return {
        "relationship_overview": base.relationship_overview or base.overview,
        "emotional_dynamic": base.emotional_dynamic,
        "communication_dynamic": base.communication_dynamic,
        "attraction_dynamic": base.attraction_dynamic,
        "power_dynamics": "Diferenças de ritmo e controle podem surgir em decisões práticas; diálogo explícito reduz atritos.",
        "growth_potential": "A relação favorece aprendizado mútuo quando expectativas são alinhadas com clareza.",
        "key_aspects": [item.model_dump() for item in (base.key_aspects or base.aspects)],
        "house_overlays": [item.model_dump() for item in base.house_overlays],
    }


@router.post("/v1/synastry/timing")
async def synastry_timing(body: SynastryCompareRequest, request: Request, auth=Depends(get_auth)):
    person_a = _build_person_chart(body.person_a, request)
    person_b = _build_person_chart(body.person_b, request)

    local_dt, _, _ = parse_local_datetime_ptbr(person_a["birth_date"], person_a["birth_time"])
    tz_offset = person_a["tz_offset_minutes"]
    base_date = datetime.utcnow().date()

    windows: List[Dict[str, Any]] = []
    for offset in (0, 7, 14, 21):
        date_ref = (base_date + timedelta(days=offset)).isoformat()
        transit = compute_transits(
            target_year=int(date_ref[:4]),
            target_month=int(date_ref[5:7]),
            target_day=int(date_ref[8:10]),
            lat=body.person_a.lat,
            lng=body.person_a.lng,
            tz_offset_minutes=tz_offset,
            zodiac_type=body.person_a.zodiac_type,
            ayanamsa=body.person_a.ayanamsa,
        )
        _, aspects_profile = get_aspects_profile()
        timing_aspects = compute_transit_aspects(
            transit_planets=transit.get("planets", {}),
            natal_planets=person_b["chart"].get("planets", {}),
            aspects=aspects_profile,
        )
        highlights = [_aspect_to_out(a).model_dump() for a in timing_aspects[:4]]
        windows.append(
            {
                "date": date_ref,
                "phase": "ativação" if offset <= 7 else "integração" if offset <= 14 else "ajuste",
                "highlights": highlights,
            }
        )

    return {
        "relationship_timing": windows,
        "metadados": {
            "timezone_usada": body.person_a.timezone or body.person_b.timezone,
            "generated_at": local_dt.isoformat(),
        },
    }


@router.post("/v1/synastry/evolution")
async def synastry_evolution(body: SynastryCompareRequest, request: Request, auth=Depends(get_auth)):
    person_a = _build_person_chart(body.person_a, request)
    person_b = _build_person_chart(body.person_b, request)

    payload = detect_relationship_evolution(
        chart_a=person_a["chart"],
        chart_b=person_b["chart"],
        lat=body.person_a.lat,
        lng=body.person_a.lng,
        tz_offset_minutes=person_a["tz_offset_minutes"],
        timezone=body.person_a.timezone or body.person_b.timezone,
    )
    return payload
