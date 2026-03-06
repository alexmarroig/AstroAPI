from __future__ import annotations

import json
from itertools import combinations, product
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

ASPECTS = ["conjunction", "square", "trine", "opposition", "sextile"]

PLANET_ARCHETYPE = {
    "sun": "identity and conscious purpose",
    "moon": "emotional memory and attachment rhythm",
    "mercury": "meaning-making, language, and mental framing",
    "venus": "values, receptivity, and relational aesthetics",
    "mars": "agency, boundary-setting, and directed action",
    "jupiter": "expansion, confidence, and worldview development",
    "saturn": "structure, accountability, and maturity",
    "uranus": "individuation, change, and liberation",
    "neptune": "imagination, empathy, and symbolic sensitivity",
    "pluto": "deep transformation and power integration",
}

SIGN_TONE = {
    "aries": "direct, initiating, and courage-oriented",
    "taurus": "grounded, stabilizing, and sensorial",
    "gemini": "curious, adaptive, and conversational",
    "cancer": "protective, receptive, and emotionally attuned",
    "leo": "expressive, creative, and self-radiant",
    "virgo": "analytical, precise, and improvement-focused",
    "libra": "relational, balancing, and reflective",
    "scorpio": "intense, psychologically probing, and regenerative",
    "sagittarius": "meaning-seeking, open-ended, and exploratory",
    "capricorn": "strategic, disciplined, and long-range",
    "aquarius": "conceptual, progressive, and system-aware",
    "pisces": "symbolic, empathic, and imaginal",
}

HOUSE_TONE = {
    1: "self-definition and personal emergence",
    2: "resources, worth, and embodied security",
    3: "learning style, communication, and immediate context",
    4: "roots, ancestry, and emotional foundation",
    5: "creativity, romance, and authentic play",
    6: "daily systems, health habits, and applied craft",
    7: "partnership dynamics and interpersonal mirroring",
    8: "shared depth, trust, and transformation processes",
    9: "belief evolution, perspective, and horizon expansion",
    10: "vocation, authority, and public contribution",
    11: "community, ideals, and collective participation",
    12: "inner retreat, closure, and unconscious integration",
}

ASPECT_TONE = {
    "conjunction": "fusion and concentrated intensity",
    "square": "dynamic tension that asks for adaptation",
    "trine": "natural flow and effortless resonance",
    "opposition": "polar awareness through relational contrast",
    "sextile": "constructive opportunity through intentional engagement",
}


def build_module(
    *,
    module_id: str,
    module_type: str,
    planet: str = "",
    sign: str = "",
    house: str = "",
    aspect: str = "",
    summary: str,
    interpretation: str,
    nuance: str,
    growth: str,
    questions: List[str],
) -> Dict[str, object]:
    return {
        "id": module_id,
        "type": module_type,
        "planet": planet,
        "sign": sign,
        "house": house,
        "aspect": aspect,
        "summary": summary,
        "interpretation": interpretation,
        "nuance": nuance,
        "growth": growth,
        "questions": questions,
    }


def make_questions(a: str, b: str) -> List[str]:
    return [
        f"How do you notice {a} shaping {b} in your current life phase?",
        "What small shift could help you respond with more awareness this week?",
    ]


def generate_planet_sign() -> List[Dict[str, object]]:
    modules = []
    for planet, sign in product(PLANETS, SIGNS):
        modules.append(
            build_module(
                module_id=f"planet_sign:{planet}_{sign}",
                module_type="planet_sign",
                planet=planet,
                sign=sign,
                summary=f"{planet.title()} in {sign.title()}",
                interpretation=(
                    f"{planet.title()} in {sign.title()} tends to express {PLANET_ARCHETYPE[planet]} "
                    f"in a {SIGN_TONE[sign]} mode."
                ),
                nuance=(
                    "This placement is a symbolic tendency rather than a fixed script; context, history, "
                    "and relational safety shape how it is lived."
                ),
                growth=(
                    f"Growth often comes from naming the needs of {planet.title()} and channeling them intentionally."
                ),
                questions=make_questions(f"{planet.title()} in {sign.title()}", "daily decisions"),
            )
        )
    return modules


def generate_planet_house() -> List[Dict[str, object]]:
    modules = []
    for planet in PLANETS:
        for house in range(1, 13):
            modules.append(
                build_module(
                    module_id=f"planet_house:{planet}_house_{house}",
                    module_type="planet_house",
                    planet=planet,
                    house=str(house),
                    summary=f"{planet.title()} in House {house}",
                    interpretation=(
                        f"{planet.title()} in House {house} highlights themes of {HOUSE_TONE[house]}."
                    ),
                    nuance=(
                        "The same placement can feel confident in one period and defensive in another; "
                        "timing and stress level matter."
                    ),
                    growth=(
                        "A practical path is to align one recurring behavior with the developmental task of this house."
                    ),
                    questions=make_questions(f"{planet.title()} in House {house}", "current priorities"),
                )
            )
    return modules


def generate_aspects() -> List[Dict[str, object]]:
    modules = []
    for p1, p2 in combinations(PLANETS, 2):
        for aspect in ASPECTS:
            modules.append(
                build_module(
                    module_id=f"aspect:{p1}_{aspect}_{p2}",
                    module_type="aspect",
                    planet=f"{p1}:{p2}",
                    aspect=aspect,
                    summary=f"{p1.title()} {aspect} {p2.title()}",
                    interpretation=(
                        f"This configuration suggests {ASPECT_TONE[aspect]} between {p1.title()} themes and {p2.title()} themes."
                    ),
                    nuance=(
                        "It may alternate between ease and friction depending on maturity, communication quality, and current transits."
                    ),
                    growth=(
                        "Integration usually improves when both poles are honored instead of idealizing one and disowning the other."
                    ),
                    questions=make_questions(
                        f"{p1.title()} {aspect} {p2.title()}",
                        "internal dialogue and external behavior",
                    ),
                )
            )
    return modules  # 225


def generate_synastry(target_count: int = 210) -> List[Dict[str, object]]:
    modules = []
    relational_lenses = [
        "emotional pacing",
        "attachment needs",
        "conflict style",
        "repair capacity",
        "intimacy rhythm",
    ]

    idx = 0
    for p1 in PLANETS:
        for p2 in PLANETS:
            if p1 == p2:
                continue
            for aspect in ASPECTS:
                lens = relational_lenses[idx % len(relational_lenses)]
                modules.append(
                    build_module(
                        module_id=f"synastry:{p1}_{aspect}_{p2}",
                        module_type="synastry",
                        planet=f"{p1}:{p2}",
                        aspect=aspect,
                        summary=f"Synastry {p1.title()} {aspect} {p2.title()}",
                        interpretation=(
                            f"In relational dynamics, this pattern can color {lens} and influence how both people co-regulate."
                        ),
                        nuance=(
                            "Compatibility is developmental, not static; awareness, consent, and emotional skills shape outcomes."
                        ),
                        growth=(
                            "A useful approach is to identify recurring triggers and co-create one explicit relational agreement."
                        ),
                        questions=make_questions(
                            f"{p1.title()} with {p2.title()}",
                            "relationship patterns",
                        ),
                    )
                )
                idx += 1
                if len(modules) >= target_count:
                    return modules
    return modules


def generate_transits(target_count: int = 250) -> List[Dict[str, object]]:
    modules = []

    transit_house_planets = ["jupiter", "saturn", "uranus", "neptune", "pluto"]
    for planet in transit_house_planets:
        for house in range(1, 13):
            modules.append(
                build_module(
                    module_id=f"transit_house:{planet}_house_{house}",
                    module_type="transit",
                    planet=planet,
                    house=str(house),
                    summary=f"{planet.title()} transiting House {house}",
                    interpretation=(
                        f"This transit period can activate {HOUSE_TONE[house]} through the lens of {PLANET_ARCHETYPE[planet]}."
                    ),
                    nuance=(
                        "Transits describe timing windows and psychological weather rather than guaranteed events."
                    ),
                    growth=(
                        "Work with this cycle by pacing expectations, tracking patterns, and choosing one conscious adjustment."
                    ),
                    questions=make_questions(
                        f"{planet.title()} transit in House {house}",
                        "current life transitions",
                    ),
                )
            )

    if len(modules) >= target_count:
        return modules[:target_count]

    transit_planets = PLANETS
    natal_targets = PLANETS
    aspect_cycle = ["conjunction", "square", "trine", "opposition"]
    for tp in transit_planets:
        for np in natal_targets:
            for aspect in aspect_cycle:
                modules.append(
                    build_module(
                        module_id=f"transit_aspect:{tp}_{aspect}_{np}",
                        module_type="transit",
                        planet=f"{tp}:{np}",
                        aspect=aspect,
                        summary=f"{tp.title()} transit {aspect} natal {np.title()}",
                        interpretation=(
                            f"When transit {tp.title()} forms a {aspect} to natal {np.title()}, "
                            "existing themes may become more visible for reflection and adjustment."
                        ),
                        nuance=(
                            "Intensity can vary by orb, context, and current developmental tasks."
                        ),
                        growth=(
                            "Use this period to make incremental choices aligned with long-term values."
                        ),
                        questions=make_questions(
                            f"{tp.title()} transit and natal {np.title()}",
                            "decision-making and regulation",
                        ),
                    )
                )
                if len(modules) >= target_count:
                    return modules
    return modules[:target_count]


def generate_archetypes(target_count: int = 200) -> List[Dict[str, object]]:
    themes = [
        "shadow awareness",
        "projection and reclaiming",
        "identity differentiation",
        "attachment repair",
        "boundary formation",
        "values clarification",
        "grief integration",
        "control and surrender",
        "vulnerability tolerance",
        "self-trust development",
        "relational reciprocity",
        "creative risk",
        "authority and agency",
        "belonging and individuation",
        "meaning reconstruction",
        "embodiment and regulation",
        "narrative reframing",
        "power and responsibility",
        "cyclical growth",
        "inner coherence",
    ]
    phases = [
        "initiation",
        "confrontation",
        "integration",
        "stabilization",
        "renewal",
        "reorientation",
        "repair",
        "discernment",
        "embodiment",
        "transformation",
    ]

    modules = []
    for theme, phase in product(themes, phases):
        modules.append(
            build_module(
                module_id=f"archetype:{theme.replace(' ', '_')}:{phase}",
                module_type="archetype",
                summary=f"{theme.title()} - {phase.title()} phase",
                interpretation=(
                    f"This archetypal pattern highlights {theme} during a {phase} process in psychological development."
                ),
                nuance=(
                    "Archetypal language is symbolic: it offers meaning frameworks, not absolute diagnoses."
                ),
                growth=(
                    "A supportive next step is to observe recurring stories and choose one action that reflects integration."
                ),
                questions=make_questions(theme, f"the {phase} phase"),
            )
        )
    return modules[:target_count]


def generate_elements(target_count: int = 100) -> List[Dict[str, object]]:
    elements = ["fire", "earth", "air", "water"]
    element_topics = [
        "motivation style",
        "stress response",
        "relational pacing",
        "decision rhythm",
        "creative expression",
        "conflict pattern",
        "self-regulation",
        "meaning orientation",
        "adaptation style",
        "resource management",
    ]
    modalities = ["cardinal", "fixed", "mutable"]
    modality_topics = [
        "initiative",
        "consistency",
        "flexibility",
        "long-term planning",
        "transition handling",
        "boundary maintenance",
        "learning style",
        "change tolerance",
        "habit formation",
        "relational movement",
    ]

    modules: List[Dict[str, object]] = []

    for element, topic in product(elements, element_topics):
        modules.append(
            build_module(
                module_id=f"elements:{element}:{topic.replace(' ', '_')}",
                module_type="elements",
                sign=element,
                summary=f"{element.title()} emphasis - {topic}",
                interpretation=(
                    f"When {element} is emphasized, {topic} may be expressed through its symbolic qualities."
                ),
                nuance=(
                    "Dominance in one element can be resourceful and limiting at once, depending on context."
                ),
                growth=(
                    "Balance develops by consciously including the underrepresented elements in daily choices."
                ),
                questions=make_questions(f"{element} emphasis", topic),
            )
        )

    for modality, topic in product(modalities, modality_topics):
        modules.append(
            build_module(
                module_id=f"modalities:{modality}:{topic.replace(' ', '_')}",
                module_type="elements",
                sign=modality,
                summary=f"{modality.title()} emphasis - {topic}",
                interpretation=(
                    f"A {modality} emphasis can shape {topic} and influence how cycles of action and adaptation unfold."
                ),
                nuance=(
                    "Modality signatures are directional tendencies, not fixed personality limits."
                ),
                growth=(
                    "Track where this style helps and where it creates blind spots, then test one balancing behavior."
                ),
                questions=make_questions(f"{modality} emphasis", topic),
            )
        )

    combo_topics = ["leadership", "intimacy", "work style", "transition phase", "inner balance"]
    for element, modality, topic in product(elements, modalities, combo_topics):
        modules.append(
            build_module(
                module_id=f"element_modality:{element}:{modality}:{topic.replace(' ', '_')}",
                module_type="elements",
                sign=f"{element}:{modality}",
                summary=f"{element.title()} + {modality.title()} pattern - {topic}",
                interpretation=(
                    f"This combination can color {topic} through {element} symbolism and {modality} pacing."
                ),
                nuance=(
                    "Expression shifts with life demands; this pattern is best read as adaptive potential."
                ),
                growth=(
                    "Develop flexibility by integrating one complementary elemental or modal strategy."
                ),
                questions=make_questions(f"{element} + {modality}", topic),
            )
        )
        if len(modules) >= target_count:
            return modules[:target_count]

    return modules[:target_count]


def write_json(path: Path, data: List[Dict[str, object]]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "seeds"
    output_dir.mkdir(parents=True, exist_ok=True)

    planet_sign = generate_planet_sign()  # 120
    planet_house = generate_planet_house()  # 120
    aspects = generate_aspects()  # 225
    synastry = generate_synastry(210)  # ~200
    transits = generate_transits(250)  # ~250
    archetypes = generate_archetypes(200)  # ~200
    elements = generate_elements(100)  # ~100

    write_json(output_dir / "modules_planet_sign.json", planet_sign)
    write_json(output_dir / "modules_planet_house.json", planet_house)
    write_json(output_dir / "modules_aspects.json", aspects)
    write_json(output_dir / "modules_synastry.json", synastry)
    write_json(output_dir / "modules_transits.json", transits)
    write_json(output_dir / "modules_archetypes.json", archetypes)
    write_json(output_dir / "modules_elements.json", elements)

    total = (
        len(planet_sign)
        + len(planet_house)
        + len(aspects)
        + len(synastry)
        + len(transits)
        + len(archetypes)
        + len(elements)
    )
    print("Generated module files:")
    print(f"modules_planet_sign.json: {len(planet_sign)}")
    print(f"modules_planet_house.json: {len(planet_house)}")
    print(f"modules_aspects.json: {len(aspects)}")
    print(f"modules_synastry.json: {len(synastry)}")
    print(f"modules_transits.json: {len(transits)}")
    print(f"modules_archetypes.json: {len(archetypes)}")
    print(f"modules_elements.json: {len(elements)}")
    print(f"TOTAL: {total}")


if __name__ == "__main__":
    main()
