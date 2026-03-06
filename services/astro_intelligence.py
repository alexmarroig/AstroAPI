from __future__ import annotations

from typing import Any, Dict, List


def _planet_map(chart: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return chart.get("planets", {}) or {}


def _distribution_map(distributions: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "elements": distributions.get("elements") or distributions.get("elementos") or {},
        "modalities": distributions.get("modalities") or distributions.get("modalidades") or {},
    }


def detect_psychological_patterns(
    *,
    chart: Dict[str, Any],
    aspects: List[Dict[str, Any]],
    distributions: Dict[str, Any],
) -> Dict[str, Any]:
    planets = _planet_map(chart)
    dists = _distribution_map(distributions)

    emotional_patterns: List[Dict[str, Any]] = []
    relationship_patterns: List[Dict[str, Any]] = []
    growth_patterns: List[Dict[str, Any]] = []

    moon = planets.get("Moon", {})
    venus = planets.get("Venus", {})
    mercury = planets.get("Mercury", {})
    sun = planets.get("Sun", {})
    mars = planets.get("Mars", {})
    saturn = planets.get("Saturn", {})

    moon_sign = str(moon.get("sign", ""))
    venus_sign = str(venus.get("sign", ""))

    if moon_sign == "Taurus" and venus_sign == "Scorpio":
        emotional_patterns.append(
            {
                "factors": ["Lua em Touro", "Vênus em Escorpião"],
                "psychological_theme": "Intensidade afetiva versus segurança emocional",
                "interpretation": "Você pode oscilar entre estabilidade e profundidade emocional intensa nos vínculos.",
                "growth_direction": "Nomear necessidades de segurança antes de entrar em dinâmicas de intensidade.",
            }
        )

    if mercury and saturn:
        relationship_patterns.append(
            {
                "factors": ["Mercúrio", "Saturno"],
                "psychological_theme": "Comunicação com filtro de responsabilidade",
                "interpretation": "Seu estilo de comunicação tende a buscar precisão, estrutura e coerência.",
                "growth_direction": "Equilibrar clareza com calor emocional para não soar excessivamente rígido.",
            }
        )

    if sun and mars:
        growth_patterns.append(
            {
                "factors": ["Sol", "Marte"],
                "psychological_theme": "Afirmação e direção de energia",
                "interpretation": "Há impulso para agir com identidade forte, especialmente em temas de autonomia.",
                "growth_direction": "Converter impulso em estratégia para sustentar constância sem exaustão.",
            }
        )

    challenging = [a for a in aspects if str(a.get("aspect", "")).lower() in {"square", "opposition"}]
    if len(challenging) >= 4:
        growth_patterns.append(
            {
                "factors": ["Cluster de aspectos tensos"],
                "psychological_theme": "Pressão evolutiva por ajustes",
                "interpretation": "Múltiplas tensões podem indicar um período interno de reorganização psicológica.",
                "growth_direction": "Priorizar uma mudança por vez e revisar respostas automáticas.",
            }
        )

    elements = dists.get("elements", {})
    modalities = dists.get("modalities", {})
    water = float(elements.get("water", 0) or elements.get("agua", 0) or 0)
    fire = float(elements.get("fire", 0) or elements.get("fogo", 0) or 0)
    fixed = float(modalities.get("fixed", 0) or modalities.get("fixo", 0) or 0)
    mutable = float(modalities.get("mutable", 0) or modalities.get("mutavel", 0) or 0)

    if water > fire * 1.6 and water > 30:
        emotional_patterns.append(
            {
                "factors": ["Predominância de Água"],
                "psychological_theme": "Profundidade emocional e sensibilidade elevada",
                "interpretation": "Você pode absorver ambientes e relações com alta intensidade afetiva.",
                "growth_direction": "Criar limites emocionais e rituais de regulação para preservar energia.",
            }
        )

    if fixed > mutable * 1.4 and fixed > 35:
        growth_patterns.append(
            {
                "factors": ["Modalidade fixa dominante"],
                "psychological_theme": "Persistência com risco de rigidez",
                "interpretation": "Existe alta capacidade de sustentação, mas possíveis resistências a mudanças de rota.",
                "growth_direction": "Praticar micro-ajustes deliberados para manter flexibilidade adaptativa.",
            }
        )

    return {
        "emotional_patterns": emotional_patterns,
        "relationship_patterns": relationship_patterns,
        "growth_patterns": growth_patterns,
    }
