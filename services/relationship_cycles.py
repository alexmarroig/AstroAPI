from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from astro.aspects import compute_transit_aspects, get_aspects_profile
from astro.ephemeris import compute_transits

SLOW_PLANETS = {"Saturn", "Uranus", "Neptune", "Pluto"}


def _phase_for(planet: str, target: str, aspect: str) -> Dict[str, str]:
    tag = f"{planet}:{target}:{aspect}".lower()
    mapping: Dict[str, Dict[str, str]] = {
        "saturn:venus:square": {
            "theme": "Teste de compromisso",
            "text": "O vínculo pode pedir maturidade emocional, acordos claros e revisão de expectativas.",
        },
        "uranus:moon:opposition": {
            "theme": "Mudança de dinâmica emocional",
            "text": "Oscilações de proximidade e espaço podem surgir, pedindo flexibilidade e diálogo honesto.",
        },
        "pluto:sun:conjunction": {
            "theme": "Transformação relacional",
            "text": "A relação pode atravessar um ciclo de intensidade e redefinição de poder pessoal.",
        },
    }
    return mapping.get(
        tag,
        {
            "theme": f"{planet} ativa {target}",
            "text": "Essa fase pode trazer ajustes de ritmo, prioridades e forma de se relacionar.",
        },
    )


def detect_relationship_evolution(
    *,
    chart_a: Dict[str, Any],
    chart_b: Dict[str, Any],
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    timezone: str | None,
) -> Dict[str, Any]:
    _, aspects_profile = get_aspects_profile()
    today = datetime.utcnow().date()

    phases: List[Dict[str, Any]] = []
    for offset in range(0, 210, 14):
        day = today + timedelta(days=offset)
        transit = compute_transits(
            target_year=day.year,
            target_month=day.month,
            target_day=day.day,
            lat=lat,
            lng=lng,
            tz_offset_minutes=tz_offset_minutes,
            zodiac_type="tropical",
            ayanamsa=None,
        )
        aspects_a = compute_transit_aspects(
            transit_planets=transit.get("planets", {}),
            natal_planets=chart_a.get("planets", {}),
            aspects=aspects_profile,
        )
        aspects_b = compute_transit_aspects(
            transit_planets=transit.get("planets", {}),
            natal_planets=chart_b.get("planets", {}),
            aspects=aspects_profile,
        )
        merged = aspects_a + aspects_b
        merged = [a for a in merged if str(a.get("transit_planet")) in SLOW_PLANETS and float(abs(a.get("orb", 99))) <= 3.5]
        if not merged:
            continue

        top = sorted(merged, key=lambda x: float(abs(x.get("orb", 99))))[0]
        t_planet = str(top.get("transit_planet", ""))
        n_target = str(top.get("natal_planet", ""))
        asp = str(top.get("aspect", ""))
        phase = _phase_for(t_planet, n_target, asp)
        phases.append(
            {
                "time_window": f"{(day - timedelta(days=10)).isoformat()} até {(day + timedelta(days=10)).isoformat()}",
                "activating_planet": t_planet,
                "synastry_target": n_target,
                "relationship_theme": phase["theme"],
                "interpretation": phase["text"],
                "peak_date": day.isoformat(),
            }
        )

    phases = sorted(phases, key=lambda p: p["peak_date"])
    current_phase = phases[0] if phases else {
        "time_window": f"{today.isoformat()} até {(today + timedelta(days=21)).isoformat()}",
        "activating_planet": "Moon",
        "synastry_target": "Venus",
        "relationship_theme": "Integração cotidiana",
        "interpretation": "Momento de consolidar presença, escuta e pequenas práticas de conexão.",
        "peak_date": today.isoformat(),
    }

    return {
        "current_phase": current_phase,
        "upcoming_phases": phases[1:8],
        "relationship_cycles": phases[:14],
        "metadados": {"timezone": timezone, "generated_at": datetime.utcnow().isoformat() + "Z"},
    }
