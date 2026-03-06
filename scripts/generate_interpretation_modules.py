from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

PLANETS = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
]

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

ASPECTS = ["conjunction", "opposition", "square", "trine", "sextile"]

TRANSIT_PLANETS = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Pluto"]
TRANSIT_TARGETS = ["Sun", "Moon", "Mercury", "Venus"]

SYNASTRY_PLANETS_A = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter"]
SYNASTRY_PLANETS_B = ["Sun", "Moon", "Venus", "Mars"]

PLANET_ARCHETYPE = {
    "Sun": "identity, vitality, and purpose",
    "Moon": "emotional rhythm, safety, and belonging",
    "Mercury": "thinking style, communication, and meaning-making",
    "Venus": "relating style, values, and receptivity",
    "Mars": "drive, boundaries, and action",
    "Jupiter": "expansion, beliefs, and growth perspective",
    "Saturn": "structure, responsibility, and maturation",
    "Uranus": "individuation, disruption, and liberation",
    "Neptune": "imagination, sensitivity, and surrender",
    "Pluto": "depth work, transformation, and power dynamics",
}

SIGN_TONE = {
    "Aries": "direct and initiating",
    "Taurus": "steady and embodied",
    "Gemini": "curious and adaptive",
    "Cancer": "protective and emotionally oriented",
    "Leo": "expressive and heart-centered",
    "Virgo": "analytical and integrative",
    "Libra": "relational and balancing",
    "Scorpio": "intense and psychologically probing",
    "Sagittarius": "meaning-seeking and exploratory",
    "Capricorn": "strategic and long-range",
    "Aquarius": "conceptual and future-oriented",
    "Pisces": "symbolic and empathic",
}

HOUSE_TONE = {
    1: "self-definition and identity expression",
    2: "resources, worth, and stabilization",
    3: "learning, communication, and local context",
    4: "roots, attachment, and inner foundations",
    5: "creativity, romance, and personal radiance",
    6: "health routines, skills, and practical service",
    7: "partnership patterns and reflective mirroring",
    8: "shared bonds, vulnerability, and renewal",
    9: "belief systems, worldview, and perspective",
    10: "vocation, visibility, and responsibility",
    11: "community, ideals, and social contribution",
    12: "closure, integration, and unconscious material",
}

ASPECT_TONE = {
    "conjunction": "merging and concentration",
    "opposition": "polarization and relational tension",
    "square": "friction that demands change",
    "trine": "natural flow and easy resonance",
    "sextile": "constructive opportunity and cooperation",
}


def _questions(a: str, b: str) -> list[str]:
    return [
        f"How do you notice {a} shaping {b} in everyday choices?",
        "What small experiment could help you respond with more awareness this week?",
    ]


def module_planet_sign(planet: str, sign: str) -> dict:
    key = f"{planet.lower()}_{sign.lower()}"
    return {
        "id": f"planet_sign:{key}",
        "type": "planet_sign",
        "planet": planet,
        "sign": sign,
        "house": "",
        "aspect": "",
        "summary": f"{planet} in {sign}",
        "interpretation": (
            f"{planet} in {sign} often expresses {PLANET_ARCHETYPE[planet]} in a "
            f"{SIGN_TONE[sign]} way."
        ),
        "nuance": (
            "This can feel different depending on life stage, context, and emotional safety; "
            "it is a tendency, not a fixed outcome."
        ),
        "growth": (
            f"Growth may come from using {planet}'s needs with intention, rather than reacting automatically."
        ),
        "questions": _questions(planet, sign),
    }


def module_planet_house(planet: str, house: int) -> dict:
    key = f"{planet.lower()}_house_{house}"
    return {
        "id": f"planet_house:{key}",
        "type": "planet_house",
        "planet": planet,
        "sign": "",
        "house": str(house),
        "aspect": "",
        "summary": f"{planet} in House {house}",
        "interpretation": (
            f"{planet} in House {house} highlights themes of {HOUSE_TONE[house]}."
        ),
        "nuance": (
            "The expression may alternate between confidence and overcompensation, especially under stress."
        ),
        "growth": (
            "A grounded step is to align daily actions with the house theme, one consistent choice at a time."
        ),
        "questions": _questions(planet, f"House {house}"),
    }


def module_aspect(p1: str, p2: str, aspect: str) -> dict:
    pair = ":".join(sorted([p1.lower(), p2.lower()]))
    return {
        "id": f"aspect:{pair}:{aspect}",
        "type": "aspect",
        "planet": pair,
        "sign": "",
        "house": "",
        "aspect": aspect,
        "summary": f"{p1} {aspect} {p2}",
        "interpretation": (
            f"This aspect suggests {ASPECT_TONE[aspect]} between {p1} themes and {p2} themes."
        ),
        "nuance": (
            "The dynamic can be experienced as supportive or challenging depending on pacing, boundaries, and timing."
        ),
        "growth": (
            "Try naming the two needs in dialogue instead of choosing one and rejecting the other."
        ),
        "questions": _questions(f"{p1} and {p2}", aspect),
    }


def module_transit(tp: str, np: str, aspect: str) -> dict:
    transit_key = f"{tp.lower()}->{np.lower()}"
    return {
        "id": f"transit:{tp.lower()}:{aspect}:{np.lower()}",
        "type": "transit",
        "planet": transit_key,
        "sign": "",
        "house": "",
        "aspect": aspect,
        "summary": f"Transit {tp} {aspect} natal {np}",
        "interpretation": (
            f"When transit {tp} forms a {aspect} to natal {np}, current events may activate this natal pattern."
        ),
        "nuance": (
            "Transits describe timing windows and psychological weather, not deterministic events."
        ),
        "growth": (
            "Use this period for conscious adjustments: pacing, communication clarity, and realistic expectations."
        ),
        "questions": _questions(f"transit {tp}", f"natal {np}"),
    }


def module_synastry(p1: str, p2: str, aspect: str) -> dict:
    return {
        "id": f"synastry:{p1.lower()}:{aspect}:{p2.lower()}",
        "type": "synastry",
        "planet": f"{p1.lower()}:{p2.lower()}",
        "sign": "",
        "house": "",
        "aspect": aspect,
        "summary": f"Synastry {p1} {aspect} {p2}",
        "interpretation": (
            f"In relationship dynamics, {p1} {aspect} {p2} can shape attraction, communication, and emotional rhythm."
        ),
        "nuance": (
            "Compatibility is developmental: awareness, consent, and emotional skills influence how this pattern unfolds."
        ),
        "growth": (
            "Name the repeating pattern together and co-create one practical relational agreement."
        ),
        "questions": _questions(f"{p1} with {p2}", "the relationship field"),
    }


def build_modules() -> list[dict]:
    modules: list[dict] = []

    for planet in PLANETS:
        for sign in SIGNS:
            modules.append(module_planet_sign(planet, sign))

    for planet in PLANETS:
        for house in range(1, 13):
            modules.append(module_planet_house(planet, house))

    for p1, p2 in combinations(PLANETS, 2):
        for aspect in ASPECTS:
            modules.append(module_aspect(p1, p2, aspect))

    for tp in TRANSIT_PLANETS:
        for np in TRANSIT_TARGETS:
            for aspect in ASPECTS:
                modules.append(module_transit(tp, np, aspect))

    for p1 in SYNASTRY_PLANETS_A:
        for p2 in SYNASTRY_PLANETS_B:
            for aspect in ASPECTS:
                modules.append(module_synastry(p1, p2, aspect))

    return modules


def to_sql(modules: list[dict]) -> str:
    values_sql = []
    for m in modules:
        content = {
            "summary": m["summary"],
            "interpretation": m["interpretation"],
            "nuance": m["nuance"],
            "growth": m["growth"],
            "questions": m["questions"],
        }
        content_json = json.dumps(content, ensure_ascii=False).replace("'", "''")

        type_sql = m["type"].replace("'", "''")
        planet_sql = m["planet"].replace("'", "''")
        sign_sql = m["sign"].replace("'", "''")
        aspect_sql = m["aspect"].replace("'", "''")
        house_sql = "NULL" if not m["house"] else str(int(m["house"]))
        id_sql = m["id"].replace("'", "''")

        values_sql.append(
            "("
            f"'{id_sql}', "
            f"'{type_sql}', "
            f"'{planet_sql}', "
            f"'{sign_sql}', "
            f"{house_sql}, "
            f"'{aspect_sql}', "
            f"'{content_json}'::jsonb"
            ")"
        )

    header = (
        "INSERT INTO public.modules (id, type, planet, sign, house, aspect, content)\nVALUES\n"
    )
    return header + ",\n".join(values_sql) + "\nON CONFLICT (id) DO NOTHING;\n"


def main() -> None:
    modules = build_modules()
    if len(modules) != 705:
        raise RuntimeError(f"Expected 705 modules, got {len(modules)}")

    output_dir = Path(__file__).resolve().parents[1] / "docs" / "seeds"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "interpretation_modules_705.json"
    sql_path = output_dir / "interpretation_modules_705.sql"

    json_path.write_text(json.dumps(modules, ensure_ascii=False, indent=2), encoding="utf-8")
    sql_path.write_text(to_sql(modules), encoding="utf-8")

    print(f"Generated {len(modules)} modules")
    print(f"JSON: {json_path}")
    print(f"SQL: {sql_path}")


if __name__ == "__main__":
    main()
