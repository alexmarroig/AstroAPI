from __future__ import annotations

from typing import Any, Dict, List

from interpretations import (
    ASPECT_INTERPRETATIONS,
    PLANET_HOUSE_INTERPRETATIONS,
    PLANET_SIGN_INTERPRETATIONS,
    SYNASTRY_INTERPRETATIONS,
    TRANSIT_INTERPRETATIONS,
)


def _key(*parts: str) -> str:
    return "_".join((p or "").strip().lower().replace(" ", "_") for p in parts if p is not None)


def _planet_sign_text(planet: str, sign: str) -> str:
    return PLANET_SIGN_INTERPRETATIONS.get(
        _key(planet, sign),
        f"{planet} em {sign} descreve um estilo próprio de expressão desta função psíquica.",
    )


def _planet_house_text(planet: str, house: Any) -> str:
    house_n = int(house) if isinstance(house, (int, float, str)) and str(house).isdigit() else None
    if house_n is None:
        return "Sem casa definida para esta posição, a leitura fica mais simbólica e menos contextual."
    return PLANET_HOUSE_INTERPRETATIONS.get(
        _key(planet, f"house_{house_n}"),
        f"{planet} na Casa {house_n} mostra onde essa energia tende a se manifestar no cotidiano.",
    )


def compose_natal_interpretation(chart: Dict[str, Any]) -> Dict[str, Any]:
    planets = chart.get("planets", {})
    sections: List[Dict[str, str]] = []

    for planet in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"):
        data = planets.get(planet)
        if not data:
            continue
        sign = str(data.get("sign", ""))
        house = data.get("house")
        short_summary = f"{planet} em {sign}."
        deep = _planet_sign_text(planet, sign)
        psych = _planet_house_text(planet, house)
        sections.append(
            {
                "planet": planet,
                "summary": short_summary,
                "deep": deep,
                "psychological": psych,
            }
        )

    summary = (
        sections[0]["deep"] if sections else "Mapa natal calculado com sucesso. Interpretação textual detalhada indisponível no momento."
    )
    return {"summary": summary, "sections": sections}


def compose_transit_interpretation(transit_item: Dict[str, Any]) -> str:
    key = _key(transit_item.get("transit_planet", ""), transit_item.get("aspect", ""), transit_item.get("natal_planet", ""))
    return ASPECT_INTERPRETATIONS.get(
        key,
        transit_item.get("description")
        or transit_item.get("influence")
        or "Este trânsito ativa um tema importante do seu mapa e pede observação consciente.",
    )


def compose_synastry_interpretation(aspect_item: Dict[str, Any]) -> str:
    key = _key(
        aspect_item.get("person1_planet", ""),
        aspect_item.get("aspect_type", ""),
        aspect_item.get("person2_planet", ""),
    )
    return SYNASTRY_INTERPRETATIONS.get(
        key,
        "Essa combinação costuma revelar padrões de vínculo, ajuste e aprendizado mútuo.",
    )


def transit_theme_lookup(theme_key: str) -> str:
    return TRANSIT_INTERPRETATIONS.get(theme_key, "O céu atual sugere ajuste de ritmo e foco em escolhas conscientes.")

