from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.interpretation_repository import InterpretationRepository


def _safe_content(module: Dict[str, Any]) -> Dict[str, Any]:
    raw = module.get("content", {}) or {}
    return {
        "summary": str(raw.get("summary", "")).strip(),
        "interpretation": str(raw.get("interpretation", "")).strip(),
        "nuance": str(raw.get("nuance", "")).strip(),
        "growth": str(raw.get("growth", "")).strip(),
    }


def _normalize_birth_chart(birth_chart: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for raw_planet, raw_data in (birth_chart or {}).items():
        if not isinstance(raw_data, dict):
            continue
        planet = str(raw_planet).strip().capitalize()
        sign = str(raw_data.get("sign", "")).strip().capitalize()
        house = raw_data.get("house")
        try:
            house_int = int(house) if house is not None else None
        except Exception:
            house_int = None
        if not planet or not sign:
            continue
        normalized[planet] = {"sign": sign, "house": house_int}
    return normalized


def _match_by_placement(modules: List[Dict[str, Any]], placements: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    seen = set()
    for module in modules:
        module_type = str(module.get("type", ""))
        planet = str(module.get("planet", "") or "").strip().capitalize()
        sign = str(module.get("sign", "") or "").strip().capitalize()
        house = module.get("house")
        try:
            house_int = int(house) if house is not None else None
        except Exception:
            house_int = None

        placement = placements.get(planet)
        if not placement:
            continue

        is_match = False
        if module_type == "planet_sign":
            is_match = bool(sign and sign == placement.get("sign"))
        elif module_type == "planet_house":
            is_match = house_int is not None and house_int == placement.get("house")

        module_id = module.get("id")
        if is_match and module_id not in seen:
            matched.append(module)
            seen.add(module_id)
    return matched


def _collect_section_text(
    modules: List[Dict[str, Any]],
    *,
    target_planets: Tuple[str, ...],
    target_houses: Tuple[int, ...] = (),
) -> str:
    chunks: List[str] = []
    for module in modules:
        planet = str(module.get("planet", "")).capitalize()
        house = module.get("house")
        try:
            house_int = int(house) if house is not None else None
        except Exception:
            house_int = None
        if planet not in target_planets and (house_int not in target_houses):
            continue
        content = _safe_content(module)
        for key in ("summary", "interpretation", "nuance", "growth"):
            text = content.get(key)
            if text and text not in chunks:
                chunks.append(text)
    return "\n".join(chunks[:8]).strip()


async def compose_module_report(birth_chart: Dict[str, Any]) -> Dict[str, str]:
    placements = _normalize_birth_chart(birth_chart)
    if not placements:
        return {
            "personality": "Dados insuficientes para compor leitura de personalidade.",
            "emotions": "Dados insuficientes para compor leitura emocional.",
            "relationships": "Dados insuficientes para compor leitura relacional.",
            "life_direction": "Dados insuficientes para compor leitura de direção de vida.",
        }

    repo = InterpretationRepository()
    all_modules = await repo._fetch_all_modules()
    matched = _match_by_placement(all_modules, placements)

    personality = _collect_section_text(
        matched,
        target_planets=("Sun", "Mercury", "Mars"),
        target_houses=(1, 3),
    )
    emotions = _collect_section_text(
        matched,
        target_planets=("Moon", "Neptune"),
        target_houses=(4, 12),
    )
    relationships = _collect_section_text(
        matched,
        target_planets=("Venus", "Moon", "Mars"),
        target_houses=(5, 7),
    )
    life_direction = _collect_section_text(
        matched,
        target_planets=("Sun", "Jupiter", "Saturn", "Pluto"),
        target_houses=(9, 10),
    )

    return {
        "personality": personality or "Nenhum módulo de personalidade encontrado para os placements informados.",
        "emotions": emotions or "Nenhum módulo emocional encontrado para os placements informados.",
        "relationships": relationships or "Nenhum módulo relacional encontrado para os placements informados.",
        "life_direction": life_direction or "Nenhum módulo de direção de vida encontrado para os placements informados.",
    }
