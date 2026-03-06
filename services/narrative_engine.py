from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from services.interpretation_repository import InterpretationRepository

ELEMENT_BY_SIGN = {
    "aries": "fire",
    "leo": "fire",
    "sagittarius": "fire",
    "taurus": "earth",
    "virgo": "earth",
    "capricorn": "earth",
    "gemini": "air",
    "libra": "air",
    "aquarius": "air",
    "cancer": "water",
    "scorpio": "water",
    "pisces": "water",
}

MODALITY_BY_SIGN = {
    "aries": "cardinal",
    "cancer": "cardinal",
    "libra": "cardinal",
    "capricorn": "cardinal",
    "taurus": "fixed",
    "leo": "fixed",
    "scorpio": "fixed",
    "aquarius": "fixed",
    "gemini": "mutable",
    "virgo": "mutable",
    "sagittarius": "mutable",
    "pisces": "mutable",
}

RULERSHIP = {
    "aries": "mars",
    "taurus": "venus",
    "gemini": "mercury",
    "cancer": "moon",
    "leo": "sun",
    "virgo": "mercury",
    "libra": "venus",
    "scorpio": "pluto",
    "sagittarius": "jupiter",
    "capricorn": "saturn",
    "aquarius": "uranus",
    "pisces": "neptune",
}

THEME_RULES = [
    {
        "id": "emotional_intensity",
        "label": "emotional intensity",
        "trigger": lambda p: p["dominant_element"] == "water" or p["has_scorpio_focus"],
        "planets": {"moon", "pluto", "venus"},
    },
    {
        "id": "intellectual_curiosity",
        "label": "intellectual curiosity",
        "trigger": lambda p: p["dominant_element"] == "air" or p["has_gemini_focus"],
        "planets": {"mercury", "moon", "uranus"},
    },
    {
        "id": "need_for_independence",
        "label": "need for independence",
        "trigger": lambda p: p["dominant_element"] == "fire" or p["has_uranus_emphasis"],
        "planets": {"sun", "mars", "uranus"},
    },
    {
        "id": "creative_expression",
        "label": "creative expression",
        "trigger": lambda p: p["houses_5_activated"] or p["has_leo_focus"],
        "planets": {"sun", "venus", "jupiter"},
    },
    {
        "id": "relationship_depth",
        "label": "relationship depth",
        "trigger": lambda p: p["houses_7_8_activated"] or p["dominant_modality"] == "fixed",
        "planets": {"venus", "moon", "saturn", "pluto"},
    },
]


def _normalize_chart_input(birth_chart: Dict[str, Any]) -> Dict[str, Any]:
    chart = birth_chart.get("chart") if isinstance(birth_chart.get("chart"), dict) else birth_chart
    planets_in = chart.get("planets", chart)
    planets: Dict[str, Dict[str, Any]] = {}

    for raw_name, raw_data in (planets_in or {}).items():
        if not isinstance(raw_data, dict):
            continue
        name = str(raw_name).strip().capitalize()
        sign = str(raw_data.get("sign", "")).strip().capitalize()
        house = raw_data.get("house")
        if not sign:
            continue
        planets[name] = {
            "sign": sign,
            "house": int(house) if isinstance(house, (int, float)) else (int(house) if str(house).isdigit() else None),
            "lon": float(raw_data.get("lon", 0.0) or 0.0),
        }

    aspects = chart.get("aspects", [])
    normalized_aspects: List[Dict[str, Any]] = []
    for aspect in aspects:
        if not isinstance(aspect, dict):
            continue
        p1 = aspect.get("planet1") or aspect.get("transit_planet")
        p2 = aspect.get("planet2") or aspect.get("natal_planet")
        if not p1 or not p2:
            continue
        normalized_aspects.append(
            {
                "planet1": str(p1).strip().capitalize(),
                "planet2": str(p2).strip().capitalize(),
                "aspect": str(aspect.get("aspect", "")).strip().lower(),
                "orb": float(aspect.get("orb", 99.0) or 99.0),
            }
        )

    return {"planets": planets, "aspects": normalized_aspects}


def _detect_patterns(chart: Dict[str, Any]) -> Dict[str, Any]:
    planets = chart.get("planets", {})
    aspects = chart.get("aspects", [])

    signs = [str(data.get("sign", "")).lower() for data in planets.values() if data.get("sign")]
    houses = [data.get("house") for data in planets.values() if data.get("house")]
    elements = [ELEMENT_BY_SIGN.get(sign) for sign in signs if ELEMENT_BY_SIGN.get(sign)]
    modalities = [MODALITY_BY_SIGN.get(sign) for sign in signs if MODALITY_BY_SIGN.get(sign)]

    dominant_element = Counter(elements).most_common(1)[0][0] if elements else "balanced"
    dominant_modality = Counter(modalities).most_common(1)[0][0] if modalities else "balanced"

    angular_planets = [planet for planet, data in planets.items() if data.get("house") in {1, 4, 7, 10}]
    sign_stellium = [sign for sign, count in Counter(signs).items() if count >= 3]
    house_stellium = [house for house, count in Counter(houses).items() if count >= 3]
    strong_aspects = sorted([a for a in aspects if abs(float(a.get("orb", 99.0))) <= 3.0], key=lambda x: abs(x["orb"]))[:8]

    rulership_count = Counter()
    for sign in signs:
        ruler = RULERSHIP.get(sign)
        if ruler and ruler.capitalize() in planets:
            rulership_count[ruler] += 1
    rulership_emphasis = rulership_count.most_common(3)

    return {
        "dominant_element": dominant_element,
        "dominant_modality": dominant_modality,
        "angular_planets": angular_planets,
        "stelliums": {"signs": sign_stellium, "houses": house_stellium},
        "strong_aspects": strong_aspects,
        "rulership_emphasis": rulership_emphasis,
        "has_scorpio_focus": "scorpio" in signs,
        "has_gemini_focus": "gemini" in signs,
        "has_leo_focus": "leo" in signs,
        "has_uranus_emphasis": any(a["planet1"] == "Uranus" or a["planet2"] == "Uranus" for a in strong_aspects),
        "houses_5_activated": 5 in houses,
        "houses_7_8_activated": 7 in houses or 8 in houses,
    }


def _derive_themes(patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
    themes = []
    for rule in THEME_RULES:
        if rule["trigger"](patterns):
            themes.append({"id": rule["id"], "label": rule["label"], "planets": rule["planets"]})
    if not themes:
        themes.append({"id": "integration_arc", "label": "integration arc", "planets": {"sun", "moon", "saturn"}})
    return themes[:5]


def _content_text(module: Dict[str, Any]) -> str:
    content = module.get("content", {}) or {}
    parts = []
    for key in ("summary", "interpretation", "nuance", "growth"):
        value = str(content.get(key, "")).strip()
        if value:
            parts.append(value)
    return " ".join(parts)


def _group_modules_by_theme(modules: List[Dict[str, Any]], themes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    assigned_ids = set()
    for theme in themes:
        theme_planets = theme["planets"]
        for module in modules:
            module_id = module.get("id")
            if module_id in assigned_ids:
                continue
            module_planet = str(module.get("planet", "")).lower()
            primary_planet = module_planet.split(":")[0] if module_planet else ""
            if primary_planet in theme_planets:
                grouped[theme["id"]].append(module)
                assigned_ids.add(module_id)
        grouped[theme["id"]] = grouped[theme["id"]][:8]
    return grouped


def _build_section(title: str, blocks: List[str]) -> str:
    merged = " ".join(b.strip() for b in blocks if b.strip())
    if not merged:
        merged = "This area suggests an ongoing process of awareness, adjustment, and integration over time."
    return f"{title}\n{merged}"


def _compose_narrative(
    patterns: Dict[str, Any],
    themes: List[Dict[str, Any]],
    grouped_modules: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    intro = _build_section(
        "Introduction",
        [
            (
                f"This chart suggests a dominant {patterns['dominant_element']} element and "
                f"{patterns['dominant_modality']} modality, indicating a recurring style of responding to life."
            ),
            (
                f"Angular emphasis appears through {', '.join(patterns['angular_planets']) or 'a subtle angular distribution'}, "
                "which may make certain themes feel more visible in day-to-day experience."
            ),
        ],
    )

    def theme_text(theme_id: str) -> str:
        modules = grouped_modules.get(theme_id, [])
        return " ".join(_content_text(m) for m in modules[:4])

    core_identity = _build_section(
        "Core identity themes",
        [theme_text("need_for_independence"), theme_text("integration_arc")],
    )
    emotional_world = _build_section(
        "Emotional world",
        [theme_text("emotional_intensity"), theme_text("intellectual_curiosity")],
    )
    relationship_patterns = _build_section(
        "Relationship patterns",
        [theme_text("relationship_depth"), theme_text("creative_expression")],
    )
    aspect_labels = [
        f"{a['planet1']} {a['aspect']} {a['planet2']}" for a in patterns["strong_aspects"][:3]
    ]
    aspect_text = ", ".join(aspect_labels) if aspect_labels else "no dominant tight aspects"
    growth = _build_section(
        "Growth and integration",
        [
            (
                "A central developmental invitation is to observe repeating emotional scripts, "
                "then introduce one deliberate choice that aligns with long-term values."
            ),
            (
                f"Strong aspects currently highlighted in this map include: "
                f"{aspect_text}."
            ),
        ],
    )
    closing = _build_section(
        "Closing reflection",
        [
            (
                "This reading is a symbolic mirror rather than a verdict. "
                "Its value lies in helping you name patterns, experiment with new responses, and build coherence over time."
            )
        ],
    )

    full_text = "\n\n".join([intro, core_identity, emotional_world, relationship_patterns, growth, closing])
    return {
        "sections": {
            "introduction": intro,
            "core_identity_themes": core_identity,
            "emotional_world": emotional_world,
            "relationship_patterns": relationship_patterns,
            "growth_and_integration": growth,
            "closing_reflection": closing,
        },
        "full_text": full_text,
        "themes": [t["label"] for t in themes],
        "patterns": patterns,
    }


async def generate_structured_narrative(birth_chart: Dict[str, Any]) -> Dict[str, Any]:
    chart = _normalize_chart_input(birth_chart)
    patterns = _detect_patterns(chart)
    themes = _derive_themes(patterns)

    repo = InterpretationRepository()
    placement_modules = await repo.find_modules_for_chart(chart)
    grouped = _group_modules_by_theme(placement_modules, themes)
    return _compose_narrative(patterns, themes, grouped)
