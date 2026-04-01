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


def get_interpretation(
    planet: str,
    sign: str | None = None,
    house: int | None = None,
    aspect_type: str | None = None,
    other_planet: str | None = None,
    context: str = "natal",  # "natal" | "synastry" | "transit"
) -> str:
    """Lookup hierárquico de interpretações. Nunca retorna string vazia."""

    # --- Nível 1: aspecto entre dois planetas (sinastria) ---
    if context == "synastry" and aspect_type and other_planet:
        key = _key(planet, aspect_type, other_planet)
        text = SYNASTRY_INTERPRETATIONS.get(key)
        if text:
            return text
        # Fallback para aspectos gerais
        text = ASPECT_INTERPRETATIONS.get(key)
        if text:
            return text

    # --- Nível 2: aspecto geral (natal/trânsito) ---
    if aspect_type and other_planet:
        key = _key(planet, aspect_type, other_planet)
        text = ASPECT_INTERPRETATIONS.get(key)
        if text:
            return text

    # --- Nível 3: planeta em signo ---
    if sign:
        text = PLANET_SIGN_INTERPRETATIONS.get(_key(planet, sign))
        if text:
            return text

    # --- Nível 4: planeta em casa ---
    if house is not None:
        text = PLANET_HOUSE_INTERPRETATIONS.get(_key(planet, f"house_{int(house)}"))
        if text:
            return text

    # --- Nível 5: fallback genérico (nunca vazio) ---
    planet_display = planet.capitalize()
    if aspect_type and other_planet:
        aspect_display = aspect_type.replace("_", " ")
        other_display = other_planet.capitalize()
        return (
            f"{planet_display} em {aspect_display} com {other_display} "
            f"ativa dinâmicas relacionais e padrões de aprendizado mútuo."
        )
    if sign:
        return f"{planet_display} em {sign.capitalize()} expressa uma qualidade própria desta função psíquica."
    if house is not None:
        return f"{planet_display} na Casa {house} mostra onde essa energia tende a se manifestar."
    return f"{planet_display} contribui com sua energia característica neste contexto."

