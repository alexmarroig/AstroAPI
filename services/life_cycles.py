from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from astro.aspects import compute_transit_aspects, get_aspects_profile
from astro.ephemeris import compute_chart, compute_transits

SLOW_PLANETS = {"Saturn", "Uranus", "Neptune", "Pluto"}
MAJOR_ASPECTS = {"conjunction", "opposition", "square", "trine", "sextile"}


@dataclass
class CycleEvent:
    planet: str
    aspect: str
    natal_target: str
    peak_date: date
    orb: float
    life_theme: str
    interpretation: str


def _theme_for(planet: str, target: str, aspect: str) -> Tuple[str, str]:
    key = f"{planet}:{target}:{aspect}".lower()
    themes: Dict[str, Tuple[str, str]] = {
        # Saturn cycles
        "saturn:moon:conjunction": (
            "Maturidade emocional",
            "Esse ciclo pede estrutura afetiva, limites claros e responsabilidade com necessidades emocionais.",
        ),
        "saturn:sun:conjunction": (
            "Reestruturação de identidade",
            "Você pode rever prioridades e compromissos, consolidando uma identidade mais realista.",
        ),
        "saturn:sun:square": (
            "Teste de estrutura pessoal",
            "Esse trânsito pede revisão de compromissos e consolidação do que é essencial na sua direção de vida.",
        ),
        "saturn:sun:opposition": (
            "Confronto com responsabilidade",
            "Período de avaliação dos resultados dos últimos anos e ajuste de metas com mais realismo.",
        ),
        "saturn:sun:trine": (
            "Consolidação de conquistas",
            "Momento favorável para estruturar planos com disciplina e colher resultados de esforços anteriores.",
        ),
        "saturn:moon:square": (
            "Revisão emocional",
            "Período de amadurecimento afetivo — padrões emocionais antigos pedem revisão e novos limites.",
        ),
        "saturn:moon:opposition": (
            "Amadurecimento afetivo",
            "Tensão entre necessidades emocionais e responsabilidades externas pede equilíbrio consciente.",
        ),
        "saturn:venus:conjunction": (
            "Revisão de relacionamentos",
            "Ciclo de amadurecimento nos vínculos — tempo para definir o que é essencial nas relações.",
        ),
        "saturn:venus:square": (
            "Testes nos vínculos",
            "Relacionamentos e valores passam por avaliações práticas — compromisso genuíno é fortalecido.",
        ),
        "saturn:mercury:conjunction": (
            "Pensamento estruturado",
            "Favorece decisões baseadas em fatos, comunicação precisa e planejamento cuidadoso.",
        ),
        # Jupiter cycles
        "jupiter:sun:trine": (
            "Expansão e oportunidade",
            "Período favorável para crescimento pessoal, reconhecimento e abertura de novos caminhos.",
        ),
        "jupiter:sun:conjunction": (
            "Novo ciclo de crescimento",
            "Aumento de vitalidade, confiança e abertura para oportunidades significativas de expansão.",
        ),
        "jupiter:sun:square": (
            "Expansão com critério",
            "Oportunidades aparecem, mas exigem discernimento — evite comprometer-se além do sustentável.",
        ),
        "jupiter:sun:sextile": (
            "Fluxo de oportunidades",
            "Momento de abertura gradual para novos projetos e conexões que ampliam seus horizontes.",
        ),
        "jupiter:moon:trine": (
            "Bem-estar emocional",
            "Período de leveza emocional, generosidade e conexão mais fácil com pessoas queridas.",
        ),
        "jupiter:moon:conjunction": (
            "Expansão emocional",
            "Aumento da sensibilidade positiva, generosidade e abertura para vínculos mais profundos.",
        ),
        "jupiter:venus:trine": (
            "Harmonia nos relacionamentos",
            "Período favorável para vínculos afetivos, prosperidade e alinhamento com o que você valoriza.",
        ),
        "jupiter:venus:conjunction": (
            "Abundância afetiva",
            "Abertura para novos relacionamentos, prazer e expressão dos seus valores mais autênticos.",
        ),
        "jupiter:venus:sextile": (
            "Oportunidades nos vínculos",
            "Favorece conexões novas, alinhamento de valores e aumento de bem-estar nas relações.",
        ),
        "jupiter:mercury:trine": (
            "Clareza e expansão mental",
            "Favorece aprendizado, comunicação inspirada e tomada de decisões com mais visão ampla.",
        ),
        # Uranus cycles
        "uranus:sun:opposition": (
            "Liberdade e reinvenção",
            "Esse período tende a ativar desejo de mudança e autonomia, com ajustes na direção de vida.",
        ),
        "uranus:sun:conjunction": (
            "Renovação radical de identidade",
            "Período de mudanças profundas na autoimagem — novas formas de se expressar emergem.",
        ),
        "uranus:sun:square": (
            "Ruptura e renovação",
            "Tensão entre o que você era e o que está se tornando — ajustes de identidade pedem coragem.",
        ),
        "uranus:sun:trine": (
            "Renovação fluida",
            "Mudanças acontecem de forma mais natural, com abertura para experimentar novas formas de ser.",
        ),
        "uranus:moon:opposition": (
            "Volatilidade emocional",
            "Padrões emocionais estabelecidos são desafiados — período de liberação de respostas automáticas.",
        ),
        "uranus:moon:conjunction": (
            "Libertação emocional",
            "Rompimento com padrões emocionais antigos — espaço para responder de forma mais autêntica.",
        ),
        "uranus:moon:square": (
            "Reorganização emocional",
            "Tensão entre necessidades de segurança e desejo de mudança pede adaptação consciente.",
        ),
        "uranus:venus:trine": (
            "Renovação nos vínculos",
            "Abertura para novas formas de relacionar e expressar afeto de maneira mais autêntica.",
        ),
        "uranus:venus:opposition": (
            "Tensão nos relacionamentos",
            "Vínculos passam por fase de revisão — autenticidade e liberdade individual pedem espaço.",
        ),
        "uranus:mercury:trine": (
            "Inovação no pensamento",
            "Período de ideias criativas, mudanças de perspectiva e abertura para novas formas de pensar.",
        ),
        "uranus:uranus:trine": (
            "Integração de mudanças",
            "Ciclo natural de integração — mudanças dos últimos anos ganham mais coerência e sentido.",
        ),
        "uranus:uranus:opposition": (
            "Ponto de virada pessoal",
            "Confronto com a própria autenticidade — período de redefinição de liberdade e valores.",
        ),
        # Neptune cycles
        "neptune:venus:trine": (
            "Sensibilidade afetiva",
            "Abertura para vínculos mais compassivos, artísticos e inspirados.",
        ),
        "neptune:sun:conjunction": (
            "Dissolução e renovação espiritual",
            "Período de questionamento de certezas — intuição e sensibilidade se aprofundam.",
        ),
        "neptune:sun:square": (
            "Niebla existencial",
            "Período de incertezas sobre direção de vida — foco em discernimento e clareza gradual.",
        ),
        "neptune:moon:conjunction": (
            "Profundidade emocional",
            "Aumento da empatia, sensibilidade e conexão com dimensões mais sutis da vida emocional.",
        ),
        "neptune:mercury:square": (
            "Desafio à clareza mental",
            "Período que pede atenção redobrada a informações — evite decisões precipitadas sem dados concretos.",
        ),
        # Pluto cycles
        "pluto:sun:square": (
            "Transformação profunda",
            "Conflitos de controle e poder podem emergir para sustentar uma mudança mais autêntica.",
        ),
        "pluto:sun:conjunction": (
            "Reinvenção total",
            "Período de morte simbólica e renascimento — identidade passa por renovação profunda.",
        ),
        "pluto:sun:trine": (
            "Transformação fluida",
            "Mudanças profundas acontecem com menos resistência — poder pessoal se consolida.",
        ),
        "pluto:sun:opposition": (
            "Confronto com poder",
            "Dinâmicas de controle e influência vêm à tona — período de reconquistar autonomia autêntica.",
        ),
        "pluto:moon:square": (
            "Transformação emocional",
            "Padrões emocionais profundos vêm à tona para transformação — processo intenso mas necessário.",
        ),
        "pluto:moon:conjunction": (
            "Renovação emocional profunda",
            "Período de confronto com padrões emocionais mais enraizados — transformação do interior.",
        ),
        "pluto:venus:conjunction": (
            "Reinvenção nos relacionamentos",
            "Vínculos passam por transformação profunda — o que não é autêntico precisa ser renovado.",
        ),
        "pluto:venus:square": (
            "Intensidade nos vínculos",
            "Relacionamentos passam por fases de intensidade e purificação — dinâmicas de poder emergem.",
        ),
        "pluto:venus:sextile": (
            "Aprofundamento dos vínculos",
            "Oportunidade de transformar relacionamentos em direção a mais autenticidade e profundidade.",
        ),
        "pluto:mercury:square": (
            "Pensamento transformador",
            "Período de questionamento profundo de crenças e formas de comunicar — renovação mental.",
        ),
        "pluto:mercury:conjunction": (
            "Mente em transformação",
            "Aprofundamento do pensamento, insights poderosos e revisão de perspectivas fundamentais.",
        ),
    }
    if key in themes:
        return themes[key]

    planet_areas = {
        "saturn": "estrutura, responsabilidade e maturidade",
        "uranus": "liberdade, mudança e autenticidade",
        "neptune": "intuição, dissolução e espiritualidade",
        "pluto": "transformação, poder pessoal e renovação",
        "jupiter": "crescimento, expansão e oportunidades",
    }
    target_areas = {
        "sun": "identidade e direção de vida",
        "moon": "vida emocional e padrões afetivos",
        "mercury": "comunicação e tomada de decisão",
        "venus": "relacionamentos e valores pessoais",
        "mars": "ação, iniciativa e energia",
        "saturn": "estrutura e compromissos",
        "jupiter": "expansão e crenças",
    }
    p_area = planet_areas.get(planet.lower(), planet.lower())
    t_area = target_areas.get(target.lower(), target.lower())
    base_theme = f"{planet} em {aspect} com {target}"
    base_text = (
        f"Esse ciclo ativa temas de {p_area} em relação à {t_area}. "
        "Favorece consciência de padrões e escolhas mais intencionais nessa área."
    )
    return base_theme, base_text


def _scan_cycle_events(
    natal_chart: Dict[str, Any],
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    zodiac_type: str,
    ayanamsa: str | None,
    from_date: date,
    to_date: date,
) -> List[CycleEvent]:
    _, aspects_profile = get_aspects_profile()
    events: Dict[Tuple[str, str, str], CycleEvent] = {}

    current = from_date
    while current <= to_date:
        transit = compute_transits(
            target_year=current.year,
            target_month=current.month,
            target_day=current.day,
            lat=lat,
            lng=lng,
            tz_offset_minutes=tz_offset_minutes,
            zodiac_type=zodiac_type,
            ayanamsa=ayanamsa,
        )
        aspects = compute_transit_aspects(
            transit_planets=transit.get("planets", {}),
            natal_planets=natal_chart.get("planets", {}),
            aspects=aspects_profile,
        )
        for asp in aspects:
            t_planet = str(asp.get("transit_planet", ""))
            aspect = str(asp.get("aspect", "")).lower()
            n_target = str(asp.get("natal_planet", ""))
            orb = float(abs(asp.get("orb", 99.0)))

            if t_planet not in SLOW_PLANETS or aspect not in MAJOR_ASPECTS:
                continue
            if orb > 3.0:
                continue

            key = (t_planet, aspect, n_target)
            theme, interpretation = _theme_for(t_planet, n_target, aspect)
            existing = events.get(key)
            if existing is None or orb < existing.orb:
                events[key] = CycleEvent(
                    planet=t_planet,
                    aspect=aspect,
                    natal_target=n_target,
                    peak_date=current,
                    orb=orb,
                    life_theme=theme,
                    interpretation=interpretation,
                )
        current += timedelta(days=7)

    return list(events.values())


def _with_window(events: List[CycleEvent]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for event in events:
        payload.append(
            {
                "planet": event.planet,
                "aspect": event.aspect,
                "natal_target": event.natal_target,
                "start_date": (event.peak_date - timedelta(days=60)).isoformat(),
                "peak_date": event.peak_date.isoformat(),
                "end_date": (event.peak_date + timedelta(days=60)).isoformat(),
                "life_theme": event.life_theme,
                "interpretation": event.interpretation,
            }
        )
    return payload


def detect_life_timeline(
    *,
    natal_year: int,
    natal_month: int,
    natal_day: int,
    natal_hour: int,
    natal_minute: int,
    natal_second: int,
    lat: float,
    lng: float,
    tz_offset_minutes: int,
    house_system: str,
    zodiac_type: str,
    ayanamsa: str | None,
    target_date: str,
) -> Dict[str, Any]:
    natal_chart = compute_chart(
        year=natal_year,
        month=natal_month,
        day=natal_day,
        hour=natal_hour,
        minute=natal_minute,
        second=natal_second,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        house_system=house_system,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
    )
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    past_from = target - timedelta(days=365 * 5)
    future_to = target + timedelta(days=365 * 5)

    events = _scan_cycle_events(
        natal_chart=natal_chart,
        lat=lat,
        lng=lng,
        tz_offset_minutes=tz_offset_minutes,
        zodiac_type=zodiac_type,
        ayanamsa=ayanamsa,
        from_date=past_from,
        to_date=future_to,
    )
    events_sorted = sorted(events, key=lambda e: e.peak_date)
    past = [e for e in events_sorted if e.peak_date < target]
    upcoming = [e for e in events_sorted if e.peak_date >= target]

    current_cycle = None
    if upcoming:
        current_cycle = _with_window([upcoming[0]])[0]
    elif past:
        current_cycle = _with_window([past[-1]])[0]

    return {
        "current_cycle": current_cycle,
        "upcoming_cycles": _with_window(upcoming[:12]),
        "past_cycles": _with_window(past[-12:]),
    }
