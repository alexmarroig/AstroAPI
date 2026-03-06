from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from astro.aspects import compute_transit_aspects, get_aspects_profile
from astro.ephemeris import compute_chart, compute_transits

SLOW_PLANETS = {"Saturn", "Uranus", "Neptune", "Pluto"}
MAJOR_ASPECTS = {"conjunction", "opposition", "square", "trine", "sextile"}


@dataclass
class CycleEvent:
    planet: str
    aspect: str
    natal_target: str
    peak_date: date
    orb: float
    life_theme: str
    interpretation: str


def _theme_for(planet: str, target: str, aspect: str) -> Tuple[str, str]:
    key = f"{planet}:{target}:{aspect}".lower()
    themes: Dict[str, Tuple[str, str]] = {
        "saturn:moon:conjunction": (
            "Maturidade emocional",
            "Esse ciclo pede estrutura afetiva, limites claros e responsabilidade com necessidades emocionais.",
        ),
        "saturn:sun:conjunction": (
            "Reestruturação de identidade",
            "Você pode rever prioridades e compromissos, consolidando uma identidade mais realista.",
        ),
        "uranus:sun:opposition": (
            "Liberdade e reinvenção",
            "Esse período tende a ativar desejo de mudança e autonomia, com ajustes na direção de vida.",
        ),
        "pluto:sun:square": (
            "Transformação profunda",
            "Conflitos de controle e poder podem emergir para sustentar uma mudança mais autêntica.",
        ),
        "neptune:venus:trine": (
            "Sensibilidade afetiva",
            "Abertura para vínculos mais compassivos, artísticos e inspirados.",
        ),
    }
    if key in themes:
        return themes[key]

    base_theme = f"{planet} em {aspect} com {target}"
    base_text = (
        "Você pode notar ajustes de ritmo, visão e prioridades. "
        "Esse trânsito favorece consciência de padrões e escolhas mais intencionais."
    )
    return base_theme, base_text


def _scan_cycle_events(
    natal_chart: Dict[str, Any],
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    zodiac_type: str,
    ayanamsa: str | None,
    from_date: date,
    to_date: date,
) -> List[CycleEvent]:
    _, aspects_profile = get_aspects_profile()
    events: Dict[Tuple[str, str, str], CycleEvent] = {}

    current = from_date
    while current <= to_date:
        transit = compute_transits(
            target_year=current.year,
            target_month=current.month,
            target_day=current.day,
            lat=lat,
            lng=lng,
            tz_offset_minutes=tz_offset_minutes,
            zodiac_type=zodiac_type,
            ayanamsa=ayanamsa,
        )
        aspects = compute_transit_aspects(
            transit_planets=transit.get("planets", {}),
            natal_planets=natal_chart.get("planets", {}),
            aspects=aspects_profile,
        )
        for asp in aspects:
            t_planet = str(asp.get("transit_planet", ""))
            aspect = str(asp.get("aspect", "")).lower()
            n_target = str(asp.get("natal_planet", ""))
            orb = float(abs(asp.get("orb", 99.0)))

            if t_planet not in SLOW_PLANETS or aspect not in MAJOR_ASPECTS:
                continue
            if orb > 3.0:
                continue

            key = (t_planet, aspect, n_target)
            theme, interpretation = _theme_for(t_planet, n_target, aspect)
            existing = events.get(key)
            if existing is None or orb < existing.orb:
                events[key] = CycleEvent(
                    planet=t_planet,
                    aspect=aspect,
                    natal_target=n_target,
                    peak_date=current,
                    orb=orb,
                    life_theme=theme,
                    interpretation=interpretation,
                )
        current += timedelta(days=7)

    return list(events.values())


def _with_window(events: List[CycleEvent]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for event in events:
        payload.append(
            {
                "planet": event.planet,
                "aspect": event.aspect,
                "natal_target": event.natal_target,
                "start_date": (event.peak_date - timedelta(days=60)).isoformat(),
                "peak_date": event.peak_date.isoformat(),
                "end_date": (event.peak_date + timedelta(days=60)).isoformat(),
                "life_theme": event.life_theme,
                "interpretation": event.interpretation,
            }
        )
    return payload


def detect_life_timeline(
    *,
    natal_year: int,
    natal_month: int,
    natal_day: int,
    natal_hour: int,
    natal_minute: int,
    natal_second: int,
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    house_system: str,
    zodiac_type: str,
    ayanamsa: str | None,
    target_date: str,
) -> Dict[str, Any]:
    natal_chart = compute_chart(
        year=natal_year,
        month=natal_month,
        day=natal_day,
        hour=natal_hour,
        minute=natal_minute,
        second=natal_second,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=house_system,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
    )
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    past_from = target - timedelta(days=365 * 5)
    future_to = target + timedelta(days=365 * 5)

    events = _scan_cycle_events(
        natal_chart=natal_chart,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
        from_date=past_from,
        to_date=future_to,
    )
    events_sorted = sorted(events, key=lambda e: e.peak_date)
    past = [e for e in events_sorted if e.peak_date < target]
    upcoming = [e for e in events_sorted if e.peak_date >= target]

    current_cycle = None
    if upcoming:
        current_cycle = _with_window([upcoming[0]])[0]
    elif past:
        current_cycle = _with_window([past[-1]])[0]

    return {
        "current_cycle": current_cycle,
        "upcoming_cycles": _with_window(upcoming[:12]),
        "past_cycles": _with_window(past[-12:]),
    }
