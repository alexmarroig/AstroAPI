from __future__ import annotations

import json
from itertools import product
from pathlib import Path
from typing import Dict, List

PLANETS = [
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
]

SIGNS = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

ASPECTS = ["conjunction", "square", "opposition", "trine", "sextile"]
HOUSES = list(range(1, 13))

PLANET_KEYWORDS = {
    "sun": "identity and vitality",
    "moon": "emotional memory and regulation",
    "mercury": "thinking and communication",
    "venus": "attachment style and values",
    "mars": "agency and boundaries",
    "jupiter": "growth and meaning",
    "saturn": "structure and responsibility",
    "uranus": "individuation and disruption",
    "neptune": "sensitivity and imagination",
    "pluto": "depth and transformation",
}

SIGN_STYLE = {
    "aries": "direct and initiating",
    "taurus": "grounded and stabilizing",
    "gemini": "curious and adaptive",
    "cancer": "protective and emotionally receptive",
    "leo": "creative and self-expressive",
    "virgo": "analytic and integrative",
    "libra": "relational and balancing",
    "scorpio": "intense and psychologically probing",
    "sagittarius": "exploratory and meaning-seeking",
    "capricorn": "strategic and long-range",
    "aquarius": "conceptual and future-oriented",
    "pisces": "symbolic and empathic",
}

HOUSE_MEANING = {
    1: "self-definition and embodiment",
    2: "resources, worth, and stability",
    3: "learning and communication habits",
    4: "roots, belonging, and emotional foundations",
    5: "creativity, romance, and personal joy",
    6: "daily routines, skill, and care practices",
    7: "partnership and relational mirroring",
    8: "intimacy, trust, and deep change",
    9: "belief systems and perspective expansion",
    10: "vocation, visibility, and responsibility",
    11: "community, friendship, and collective vision",
    12: "inner retreat, closure, and unconscious material",
}

ASPECT_DYNAMICS = {
    "conjunction": "fusion and concentration of psychic energy",
    "square": "productive friction that demands adaptation",
    "opposition": "polar tension seeking dialogue and balance",
    "trine": "natural flow and ease in expression",
    "sextile": "constructive opportunity through intentional effort",
}

LENSES = [
    "attachment patterns",
    "identity development",
    "conflict regulation",
    "creative expression",
    "boundary maintenance",
    "meaning-making",
    "self-trust",
    "vulnerability tolerance",
    "power dynamics",
    "integration work",
]


def module(
    *,
    module_id: str,
    module_type: str,
    planet: str = "",
    sign: str = "",
    house: str = "",
    aspect: str = "",
    theme: str,
    summary: str,
    interpretation: str,
    shadow: str,
    integration: str,
    questions: List[str],
) -> Dict[str, object]:
    return {
        "id": module_id,
        "type": module_type,
        "planet": planet,
        "sign": sign,
        "house": house,
        "aspect": aspect,
        "theme": theme,
        "summary": summary,
        "interpretation": interpretation,
        "shadow": shadow,
        "integration": integration,
        "questions": questions,
    }


def q(a: str, b: str) -> List[str]:
    return [
        f"When do you notice {a} shaping {b} most strongly?",
        "What small, realistic practice could support a more integrated response this week?",
    ]


def gen_planet_sign() -> List[Dict[str, object]]:
    out = []
    for p, s in product(PLANETS, SIGNS):
        out.append(
            module(
                module_id=f"planet_sign:{p}_{s}",
                module_type="planet_sign",
                planet=p,
                sign=s,
                theme=f"{p} expression through {s} style",
                summary=f"{p.title()} in {s.title()}",
                interpretation=(
                    f"This placement suggests {PLANET_KEYWORDS[p]} expressed in a {SIGN_STYLE[s]} tone. "
                    "It often describes a symbolic orientation rather than a fixed destiny."
                ),
                shadow=(
                    "Under stress, this pattern may become rigid, defensive, or over-identified with one coping style."
                ),
                integration=(
                    "Integration grows through conscious pacing, self-observation, and choices aligned with values."
                ),
                questions=q(f"{p.title()} in {s.title()}", "your day-to-day decisions"),
            )
        )
    return out


def gen_planet_house() -> List[Dict[str, object]]:
    out = []
    for p in PLANETS:
        for h in HOUSES:
            out.append(
                module(
                    module_id=f"planet_house:{p}_house_{h}",
                    module_type="planet_house",
                    planet=p,
                    house=str(h),
                    theme=f"{p} developmental work in house {h}",
                    summary=f"{p.title()} in House {h}",
                    interpretation=(
                        f"{p.title()} in House {h} highlights {HOUSE_MEANING[h]}. "
                        "It shows where growth themes tend to become visible in lived experience."
                    ),
                    shadow=(
                        "The challenge can appear as overcontrol, avoidance, or repetition of familiar emotional scripts."
                    ),
                    integration=(
                        "A grounded path is to connect one practical behavior to this house theme and repeat it consistently."
                    ),
                    questions=q(f"{p.title()} in House {h}", "current life priorities"),
                )
            )
    return out


def gen_aspects() -> List[Dict[str, object]]:
    out = []
    for p1, p2, a in product(PLANETS, PLANETS, ASPECTS):
        out.append(
            module(
                module_id=f"aspect:{p1}_{a}_{p2}",
                module_type="aspect",
                planet=f"{p1}:{p2}",
                aspect=a,
                theme=f"{p1} and {p2} in {a} dynamic",
                summary=f"{p1.title()} {a} {p2.title()}",
                interpretation=(
                    f"This aspect reflects {ASPECT_DYNAMICS[a]} between {p1.title()} themes and {p2.title()} themes. "
                    "It can become a key pattern in personality organization."
                ),
                shadow=(
                    "In reactive states, the polarity may split into all-or-nothing narratives and repetitive conflict loops."
                ),
                integration=(
                    "Integration comes from naming both needs with honesty and allowing dialogue instead of internal polarization."
                ),
                questions=q(f"{p1.title()} {a} {p2.title()}", "inner and relational dynamics"),
            )
        )
    return out  # 500


def gen_synastry() -> List[Dict[str, object]]:
    out = []
    for p1, p2, a in product(PLANETS, PLANETS, ASPECTS):
        out.append(
            module(
                module_id=f"synastry:{p1}_{a}_{p2}",
                module_type="synastry",
                planet=f"{p1}:{p2}",
                aspect=a,
                theme=f"relational dynamic: {p1}-{p2} {a}",
                summary=f"Synastry {p1.title()} {a} {p2.title()}",
                interpretation=(
                    f"In relationship, this pattern can shape emotional rhythm, communication style, and expectations of closeness. "
                    "It points to a field of learning rather than a final verdict."
                ),
                shadow=(
                    "Without reflection, partners may replay projection patterns, misattunement, or defensive reciprocity."
                ),
                integration=(
                    "A useful step is to co-name triggers, clarify needs, and build repair rituals after moments of rupture."
                ),
                questions=q(f"{p1.title()} {a} {p2.title()}", "the relationship process"),
            )
        )
    return out  # 500


def gen_transits() -> List[Dict[str, object]]:
    out = []

    # 1) Planet transiting houses: 10 * 12 = 120
    for p, h in product(PLANETS, HOUSES):
        out.append(
            module(
                module_id=f"transit_house:{p}_house_{h}",
                module_type="transit",
                planet=p,
                house=str(h),
                theme=f"{p} transit through house {h}",
                summary=f"{p.title()} transiting House {h}",
                interpretation=(
                    f"This transit can amplify themes of {HOUSE_MEANING[h]} through {PLANET_KEYWORDS[p]}. "
                    "It describes timing and emphasis, not deterministic outcomes."
                ),
                shadow=(
                    "Pressure may show up as urgency, avoidance, or over-identification with short-term narratives."
                ),
                integration=(
                    "Work with this cycle by pacing decisions and tracking what repeatedly asks for attention."
                ),
                questions=q(f"{p.title()} in House {h}", "current transitions"),
            )
        )

    # 2) Planet transiting planets: 9 (without Moon) * 10 * 5 = 450
    transit_planets = [p for p in PLANETS if p != "moon"]
    for tp, np, a in product(transit_planets, PLANETS, ASPECTS):
        out.append(
            module(
                module_id=f"transit_aspect:{tp}_{a}_{np}",
                module_type="transit",
                planet=f"{tp}:{np}",
                aspect=a,
                theme=f"{tp} transit {a} natal {np}",
                summary=f"{tp.title()} transit {a} natal {np.title()}",
                interpretation=(
                    "This configuration may activate a familiar internal pattern, inviting awareness and recalibration."
                ),
                shadow=(
                    "If unexamined, the transit can intensify habitual defenses or reactive communication loops."
                ),
                integration=(
                    "Pause, name the pattern, and choose one behavior that aligns with long-term psychological integration."
                ),
                questions=q(f"{tp.title()} transit {a} {np.title()}", "your current developmental cycle"),
            )
        )

    # 3) Major life cycles: 30 modules
    cycles = [
        ("saturn_return", "saturn", "identity consolidation cycle"),
        ("saturn_opposition", "saturn", "mid-cycle accountability process"),
        ("uranus_opposition", "uranus", "individuation and reinvention period"),
        ("chiron_return", "chiron", "healing narrative reorganization"),
        ("nodal_return", "nodes", "directional realignment cycle"),
        ("pluto_square_sun", "pluto", "deep transformation pressure"),
    ]
    for i in range(30):
        key, planet, theme = cycles[i % len(cycles)]
        lens = LENSES[i % len(LENSES)]
        out.append(
            module(
                module_id=f"life_cycle:{key}:{i+1}",
                module_type="transit",
                planet=planet,
                theme=f"{theme} - {lens}",
                summary=f"Life cycle: {key.replace('_', ' ').title()}",
                interpretation=(
                    "This longer cycle often marks a phase of restructuring, meaning revision, and maturity through lived experience."
                ),
                shadow=(
                    "Shadow expression can appear as rigidity, overwhelm, or clinging to outdated identity structures."
                ),
                integration=(
                    "Integration is supported by incremental change, honest feedback, and values-based decision making."
                ),
                questions=q(key.replace("_", " "), lens),
            )
        )

    return out  # 600


def gen_archetypes() -> List[Dict[str, object]]:
    themes = [
        "identity differentiation",
        "self-worth reconstruction",
        "attachment repair",
        "power negotiation",
        "creative emergence",
        "authority integration",
        "embodied regulation",
        "narrative reframing",
        "shadow encounter",
        "inner child attunement",
        "grief metabolization",
        "boundary intelligence",
        "belonging and individuation",
        "relational reciprocity",
        "intimacy tolerance",
        "vocation alignment",
        "value integration",
        "existential meaning",
        "trust rebuilding",
        "resilience development",
        "projection retrieval",
        "purpose clarification",
        "fear integration",
        "hope reorganization",
        "maturation through limits",
        "freedom and responsibility",
        "repair after rupture",
        "forgiveness process",
        "creative risk regulation",
        "leadership ethics",
        "emotional literacy",
        "conflict transformation",
        "life direction calibration",
        "symbolic imagination",
        "transpersonal perspective",
    ]  # 35
    phases = [
        "awakening",
        "naming",
        "confrontation",
        "containment",
        "deconstruction",
        "dialogue",
        "repair",
        "integration",
        "embodiment",
        "stabilization",
        "renewal",
        "reorientation",
        "practice",
        "discernment",
        "release",
        "reclaiming",
        "coherence",
        "alignment",
        "service",
        "transformation",
    ]  # 20

    out = []
    for t, p in product(themes, phases):
        out.append(
            module(
                module_id=f"archetype:{t.replace(' ', '_')}:{p}",
                module_type="archetype",
                theme=f"{t} - {p}",
                summary=f"{t.title()} ({p})",
                interpretation=(
                    "This archetypal configuration points to a developmental process where symbolic meaning and lived behavior can be re-linked."
                ),
                shadow=(
                    "Shadow may appear as repetition of protective strategies that once helped but now limit psychological movement."
                ),
                integration=(
                    "Integration grows through sustained self-reflection, relational feedback, and embodied action over time."
                ),
                questions=q(t, p),
            )
        )
    return out  # 700


def gen_elements() -> List[Dict[str, object]]:
    elements = ["fire", "earth", "air", "water"]
    modalities = ["cardinal", "fixed", "mutable"]
    topics = [
        "motivation",
        "stress regulation",
        "decision style",
        "relationship pacing",
        "creative process",
        "conflict handling",
        "energy management",
        "meaning orientation",
        "adaptation pattern",
        "recovery rhythm",
        "communication tempo",
        "boundary style",
        "self-image",
        "work behavior",
        "future planning",
        "emotional processing",
        "integration strategy",
        "life transitions",
        "leadership style",
        "coherence building",
    ]

    out = []

    # 80 element modules
    for e, t in product(elements, topics):
        out.append(
            module(
                module_id=f"elements:{e}:{t.replace(' ', '_')}",
                module_type="elements",
                sign=e,
                theme=f"{e} emphasis in {t}",
                summary=f"{e.title()} dominance - {t}",
                interpretation=(
                    f"A {e} emphasis may shape {t} with its symbolic qualities, offering both strengths and blind spots."
                ),
                shadow=(
                    "When unbalanced, this emphasis may over-rely on familiar coping modes and underuse complementary functions."
                ),
                integration=(
                    "Balance can be cultivated by intentionally practicing the underrepresented elements in small routines."
                ),
                questions=q(f"{e} dominance", t),
            )
        )

    # 60 modality modules
    for m, t in product(modalities, topics):
        out.append(
            module(
                module_id=f"modalities:{m}:{t.replace(' ', '_')}",
                module_type="elements",
                sign=m,
                theme=f"{m} emphasis in {t}",
                summary=f"{m.title()} emphasis - {t}",
                interpretation=(
                    f"A {m} pattern can influence how {t} unfolds across cycles of initiation, maintenance, and adaptation."
                ),
                shadow=(
                    "Over-identification may lead to rigidity, impulsivity, or diffusion depending on context."
                ),
                integration=(
                    "Integration is supported by pacing adjustments and conscious use of alternate modal strategies."
                ),
                questions=q(f"{m} emphasis", t),
            )
        )

    # 60 element+modality modules
    combo_topics = ["identity", "relationships", "work", "change", "inner balance"]
    for e, m, t in product(elements, modalities, combo_topics):
        out.append(
            module(
                module_id=f"element_modality:{e}:{m}:{t}",
                module_type="elements",
                sign=f"{e}:{m}",
                theme=f"{e} + {m} pattern in {t}",
                summary=f"{e.title()} + {m.title()} pattern - {t}",
                interpretation=(
                    "This symbolic blend can shape how energy is mobilized, sustained, and redirected in this life area."
                ),
                shadow=(
                    "The challenge may appear as repetitive strategy loops that feel familiar but reduce flexibility."
                ),
                integration=(
                    "A useful practice is to pair this dominant style with one complementary behavior from another mode."
                ),
                questions=q(f"{e} and {m}", t),
            )
        )

    return out  # 200


def write_json(path: Path, data: List[Dict[str, object]]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "seeds" / "v3_3000"
    output_dir.mkdir(parents=True, exist_ok=True)

    modules_planet_sign = gen_planet_sign()  # 120
    modules_planet_house = gen_planet_house()  # 120
    modules_aspects = gen_aspects()  # 500
    modules_synastry = gen_synastry()  # 500
    modules_transits = gen_transits()  # 600
    modules_archetypes = gen_archetypes()  # 700
    modules_elements = gen_elements()  # 200

    write_json(output_dir / "modules_planet_sign.json", modules_planet_sign)
    write_json(output_dir / "modules_planet_house.json", modules_planet_house)
    write_json(output_dir / "modules_aspects.json", modules_aspects)
    write_json(output_dir / "modules_synastry.json", modules_synastry)
    write_json(output_dir / "modules_transits.json", modules_transits)
    write_json(output_dir / "modules_archetypes.json", modules_archetypes)
    write_json(output_dir / "modules_elements.json", modules_elements)

    total = (
        len(modules_planet_sign)
        + len(modules_planet_house)
        + len(modules_aspects)
        + len(modules_synastry)
        + len(modules_transits)
        + len(modules_archetypes)
        + len(modules_elements)
    )

    print(f"modules_planet_sign.json: {len(modules_planet_sign)}")
    print(f"modules_planet_house.json: {len(modules_planet_house)}")
    print(f"modules_aspects.json: {len(modules_aspects)}")
    print(f"modules_synastry.json: {len(modules_synastry)}")
    print(f"modules_transits.json: {len(modules_transits)}")
    print(f"modules_archetypes.json: {len(modules_archetypes)}")
    print(f"modules_elements.json: {len(modules_elements)}")
    print(f"TOTAL: {total}")
    print(f"DIR: {output_dir}")


if __name__ == "__main__":
    main()
