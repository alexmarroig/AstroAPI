from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from astro.aspects import compute_transit_aspects, get_aspects_profile
from services.astro_logic import get_house_for_lon

QUESTION_RULES: Dict[str, Dict[str, Any]] = {
    "career": {
        "houses": {10, 6},
        "planets": {"Sun", "Mars", "Saturn", "Jupiter"},
        "prompt": "carreira, trabalho, responsabilidade e execucao.",
    },
    "relationship": {
        "houses": {5, 7},
        "planets": {"Venus", "Moon", "Mars"},
        "prompt": "vinculo, afeto, reciprocidade e limites.",
    },
    "communication": {
        "houses": {3},
        "planets": {"Mercury", "Moon", "Jupiter"},
        "prompt": "comunicacao, clareza, escuta e alinhamento.",
    },
    "personal_growth": {
        "houses": {1, 9},
        "planets": {"Sun", "Jupiter", "Saturn", "Pluto"},
        "prompt": "crescimento, identidade e integracao de experiencias.",
    },
    "decision_timing": {
        "houses": {1, 10},
        "planets": {"Mercury", "Mars", "Saturn", "Jupiter"},
        "prompt": "timing, estrategia e qualidade de decisao.",
    },
}

QUESTION_KEYWORDS: Dict[str, List[str]] = {
    "career": ["trabalho", "carreira", "projeto", "promocao", "negocio", "job", "career"],
    "relationship": ["relacao", "namoro", "casamento", "parceiro", "amor", "relationship"],
    "communication": ["conversa", "comunic", "mensagem", "negoci", "fala", "mercurio", "communication"],
    "personal_growth": ["crescimento", "proposito", "mudanca", "autoconhecimento", "growth"],
    "decision_timing": ["agora", "momento", "decidir", "timing", "quando", "esperar"],
}

INFLUENCE_LABELS = {
    "supportive": "apoio",
    "fluid influence": "fluido",
    "challenging": "desafiador",
    "challenging influence": "desafiador",
    "intense": "intenso",
    "intense influence": "intenso",
    "subtle": "sutil",
    "adjusting": "ajuste",
}


@dataclass
class InfluenceItem:
    title: str
    score: float
    text: str


def classify_question(question: str, explicit_type: Optional[str] = None) -> str:
    if explicit_type and explicit_type in QUESTION_RULES:
        return explicit_type

    q = (question or "").lower()
    ranking: List[Tuple[str, int]] = []
    for key, keywords in QUESTION_KEYWORDS.items():
        hit = sum(1 for token in keywords if token in q)
        ranking.append((key, hit))

    ranking.sort(key=lambda item: item[1], reverse=True)
    if ranking and ranking[0][1] > 0:
        return ranking[0][0]
    return "decision_timing"


def _normalized_influence_label(value: str) -> str:
    return INFLUENCE_LABELS.get(value.strip().lower(), value.strip().lower() or "neutro")


def _format_influence_title(aspect: Dict[str, Any]) -> str:
    t_planet = str(aspect.get("transit_planet", "Transito"))
    asp = str(aspect.get("aspect", "aspecto")).lower()
    n_planet = str(aspect.get("natal_planet", "ponto natal"))
    return f"{t_planet} {asp} {n_planet}"


def _score_aspect(
    aspect: Dict[str, Any],
    rules: Dict[str, Any],
    houses: List[float],
) -> float:
    orb = abs(float(aspect.get("orb", 8.0)))
    base = max(0.0, 10.0 - orb)

    t_planet = str(aspect.get("transit_planet", ""))
    n_planet = str(aspect.get("natal_planet", ""))
    if t_planet in rules["planets"] or n_planet in rules["planets"]:
        base += 5.0

    n_data_house = int(aspect.get("natal_house", 0) or 0)
    if n_data_house and n_data_house in rules["houses"]:
        base += 4.0
    elif houses:
        transit_lon = float(aspect.get("transit_lon", 0.0) or 0.0)
        activated = int(get_house_for_lon(houses, transit_lon))
        if activated in rules["houses"]:
            base += 3.0

    if t_planet in {"Saturn", "Pluto", "Neptune", "Uranus"}:
        base += 2.0
    if t_planet in {"Sun", "Moon"} or n_planet in {"Sun", "Moon"}:
        base += 2.0

    return round(base, 2)


def _extract_active_influences(
    user_chart: Dict[str, Any],
    current_transits: Dict[str, Any],
    question_type: str,
) -> List[InfluenceItem]:
    _, aspects_profile = get_aspects_profile()
    aspects = compute_transit_aspects(
        transit_planets=current_transits.get("planets", {}),
        natal_planets=user_chart.get("planets", {}),
        aspects=aspects_profile,
    )
    rules = QUESTION_RULES[question_type]
    houses = user_chart.get("houses", {}).get("cusps", [])

    items: List[InfluenceItem] = []
    for asp in aspects:
        score = _score_aspect(asp, rules, houses)
        if score < 5:
            continue
        influence = _normalized_influence_label(str(asp.get("influence", "")))
        orb = round(abs(float(asp.get("orb", 0.0))), 2)
        title = _format_influence_title(asp)
        text = f"Tonalidade {influence} com orb {orb}."
        items.append(InfluenceItem(title=title, score=score, text=text))

    items.sort(key=lambda item: item.score, reverse=True)
    return items[:6]


def _extract_slow_cycles(active_life_cycles: Optional[Dict[str, Any]]) -> List[str]:
    if not active_life_cycles:
        return []
    entries = []
    current = active_life_cycles.get("current_cycle")
    if current:
        entries.append(
            f"{current.get('planet', 'Ciclo')} {current.get('aspect', 'ativo')} {current.get('natal_target', '')}".strip()
        )
    for cycle in (active_life_cycles.get("upcoming_cycles") or [])[:2]:
        entries.append(
            f"{cycle.get('planet', 'Ciclo')} {cycle.get('aspect', 'ativo')} {cycle.get('natal_target', '')}".strip()
        )
    return entries


def _build_reflective_guidance(
    question_type: str,
    influences: List[InfluenceItem],
    slow_cycles: List[str],
    has_synastry: bool,
) -> Tuple[str, str, str]:
    rules = QUESTION_RULES[question_type]
    top = influences[0].title if influences else "Cenario cosmico em ajuste gradual"
    context = f"{top} indica foco em {rules['prompt']}"

    guidance = (
        "Este periodo pode favorecer decisoes mais consistentes quando ha clareza de prioridade, "
        "ritmo sustentavel e revisao de expectativas."
    )
    if slow_cycles:
        guidance += " Ciclos lentos ativos sugerem estrategia de medio prazo."
    if has_synastry:
        guidance += " A dinamica relacional adiciona nuances de alinhamento e timing."

    reflection = (
        "Qual parte dessa decisao depende de acao imediata, e qual parte pede consolidacao progressiva?"
    )
    return context, guidance, reflection


def analyze_context(
    user_chart: Dict[str, Any],
    current_transits: Dict[str, Any],
    question_context: Dict[str, Any],
    active_life_cycles: Optional[Dict[str, Any]] = None,
    synastry_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    question = str(question_context.get("question", ""))
    question_type = classify_question(question, question_context.get("question_type"))

    influences = _extract_active_influences(user_chart, current_transits, question_type)
    slow_cycles = _extract_slow_cycles(active_life_cycles)

    key_influences = [item.title for item in influences[:4]]
    key_influences.extend([cycle for cycle in slow_cycles if cycle not in key_influences])
    key_influences = key_influences[:6] or ["Transitos moderados em fase de observacao."]

    current_context, reflective_guidance, suggested_reflection = _build_reflective_guidance(
        question_type=question_type,
        influences=influences,
        slow_cycles=slow_cycles,
        has_synastry=synastry_context is not None,
    )

    return {
        "current_cosmic_context": current_context,
        "key_influences": key_influences,
        "reflective_guidance": reflective_guidance,
        "suggested_reflection": suggested_reflection,
        "question_type": question_type,
    }
