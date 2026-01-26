from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Literal

from astro.ephemeris import PLANETS, compute_chart, compute_transits, compute_moon_only
from schemas.alerts import SystemAlert
from astro.i18n_ptbr import (
    aspect_to_ptbr,
    planet_key_to_ptbr,
    sign_to_ptbr,
    format_degree_ptbr,
)
from astro.utils import angle_diff, sign_to_pt, ZODIAC_SIGNS, ZODIAC_SIGNS_PT
from schemas.transits import (
    TransitEvent,
    TransitEventDateRange,
    TransitEventCopy,
    PreferenciasPerfil,
    TransitsRequest
)
from schemas.solar_return import SolarReturnPreferencias

# --- Mapas de Elementos, Modalidades e Regentes ---
ELEMENT_MAP = {
    "Aries": "Fogo", "Leo": "Fogo", "Sagittarius": "Fogo",
    "Taurus": "Terra", "Virgo": "Terra", "Capricorn": "Terra",
    "Gemini": "Ar", "Libra": "Ar", "Aquarius": "Ar",
    "Cancer": "Água", "Scorpio": "Água", "Pisces": "Água",
}

MODALITY_MAP = {
    "Aries": "Cardinal", "Cancer": "Cardinal", "Libra": "Cardinal", "Capricorn": "Cardinal",
    "Taurus": "Fixo", "Leo": "Fixo", "Scorpio": "Fixo", "Aquarius": "Fixo",
    "Gemini": "Mutável", "Virgo": "Mutável", "Sagittarius": "Mutável", "Pisces": "Mutável",
}

RULER_MAP = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# --- Pesos e Configurações para Scoring de Impacto ---
PLANET_WEIGHTS = {
    "Moon": 1.0, "Mercury": 1.5, "Venus": 1.5, "Sun": 1.5, "Mars": 2.2,
    "Jupiter": 2.5, "Saturn": 3.3, "Uranus": 3.0, "Neptune": 3.0, "Pluto": 3.6,
}

ASPECT_WEIGHTS = {
    "conjunction": 1.0, "opposition": 0.95, "square": 0.95, "trine": 0.70, "sextile": 0.55,
}

TARGET_WEIGHTS = {
    "Sun": 1.25, "Moon": 1.25, "ASC": 1.25, "MC": 1.25,
}

DURATION_FACTORS = {
    "Moon": 0.85, "Mercury": 0.85, "Venus": 0.85, "Sun": 0.85, "Mars": 0.90,
    "Jupiter": 1.00, "Saturn": 1.00, "Uranus": 1.00, "Neptune": 1.00, "Pluto": 1.00,
}

# --- Tags para Eventos ---
PLANET_TAGS = {
    "Sun": ["Identidade", "Direção"], "Moon": ["Emoções", "Necessidades"],
    "Mercury": ["Comunicação", "Decisão"], "Venus": ["Relacionamentos", "Valor"],
    "Mars": ["Ação", "Coragem"], "Jupiter": ["Expansão", "Oportunidade"],
    "Saturn": ["Estrutura", "Responsabilidade"], "Uranus": ["Mudança", "Ruptura"],
    "Neptune": ["Inspiração", "Sensibilidade"], "Pluto": ["Transformação", "Intensidade"],
}

ASPECT_TAGS = {
    "conjunction": ["Intensidade"], "opposition": ["Tensão"],
    "square": ["Ajuste"], "trine": ["Fluxo"], "sextile": ["Abertura"],
}

PROFILE_DEFAULT_ASPECTS = ["conj", "opos", "quad", "tri", "sext"]
PROFILE_DEFAULT_ORB_MAX = 5.0

def get_house_for_lon(cusps: List[float], lon: float) -> int:
    """
    Calcula em qual casa astrológica uma determinada longitude se encontra.
    Baseia-se nas cúspides das casas fornecidas (geralmente 12).
    """
    if not cusps:
        return 1
    lon_mod = lon % 360
    for idx in range(12):
        start = float(cusps[idx])
        end = float(cusps[(idx + 1) % 12])
        start_mod = start
        end_mod = end
        lon_check = lon_mod
        if end_mod < start_mod:
            end_mod += 360
            if lon_check < start_mod:
                lon_check += 360
        if start_mod <= lon_check < end_mod:
            return idx + 1
    return 12

def calculate_distributions(chart: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calcula o equilíbrio de elementos (Fogo, Terra, Ar, Água) e modalidades (Cardinal, Fixo, Mutável).
    Também conta a ocupação dos planetas em cada uma das 12 casas.
    """
    elements = {"Fogo": 0, "Terra": 0, "Ar": 0, "Água": 0}
    modalities = {"Cardinal": 0, "Fixo": 0, "Mutável": 0}
    houses_counts = {house: {"casa": house, "contagem": 0, "planetas": []} for house in range(1, 13)}
    avisos: List[str] = []

    cusps = chart.get("houses", {}).get("cusps") or []
    planets = chart.get("planets", {})

    for name in PLANETS.keys():
        planet = planets.get(name)
        if not planet:
            avisos.append(f"Planeta ausente: {name}.")
            continue
        sign = planet.get("sign")
        lon = planet.get("lon")
        if sign is None or lon is None:
            avisos.append(f"Sem signo/longitude para {name}.")
            continue

        element = ELEMENT_MAP.get(sign)
        modality = MODALITY_MAP.get(sign)
        if element:
            elements[element] += 1
        else:
            avisos.append(f"Elemento não mapeado para {name}.")
        if modality:
            modalities[modality] += 1
        else:
            avisos.append(f"Modalidade não mapeada para {name}.")

        house = get_house_for_lon(cusps, float(lon))
        houses_counts[house]["contagem"] += 1
        houses_counts[house]["planetas"].append(planet_key_to_ptbr(name))

    dominant_element = max(elements.items(), key=lambda item: item[1])[0]
    dominant_modality = max(modalities.items(), key=lambda item: item[1])[0]
    houses_sorted = sorted(houses_counts.values(), key=lambda item: item["contagem"], reverse=True)
    top_houses = [item["casa"] for item in houses_sorted[:3]]

    payload = {
        "elementos": elements,
        "modalidades": modalities,
        "casas": list(houses_counts.values()),
        "dominancias": {
            "elemento_dominante": dominant_element,
            "modalidade_dominante": dominant_modality,
            "casas_mais_ativadas": top_houses,
        },
        "metadados": metadata or {},
    }
    if avisos:
        payload["avisos"] = avisos
    return payload

def get_impact_score(transit_planet: str, aspect: str, target: str, orb_deg: float, orb_max: float) -> float:
    """Calcula o score de impacto de um aspecto de trânsito."""
    if orb_max <= 0:
        orb_max = PROFILE_DEFAULT_ORB_MAX
    planet_weight = PLANET_WEIGHTS.get(transit_planet, 1.0)
    aspect_weight = ASPECT_WEIGHTS.get(aspect, 0.5)
    target_weight = TARGET_WEIGHTS.get(target, 1.0)
    duration_factor = DURATION_FACTORS.get(transit_planet, 1.0)
    orb_factor = max(0.0, min(1.0, 1.0 - (orb_deg / orb_max)))
    score = 100 * planet_weight * aspect_weight * target_weight * orb_factor * duration_factor
    return round(min(score, 100.0), 2)

def get_severity_for_score(score: float) -> str:
    """Retorna a severidade (BAIXA, MEDIA, ALTA) com base no score de impacto."""
    if score >= 70: return "ALTA"
    if score >= 45: return "MEDIA"
    return "BAIXA"

def get_event_tags(transit_planet: str, aspect: str) -> List[str]:
    """Retorna as tags associadas a um planeta e um aspecto."""
    tags = []
    tags.extend(PLANET_TAGS.get(transit_planet, []))
    tags.extend(ASPECT_TAGS.get(aspect, []))
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result[:4]

def build_transit_event(aspect: Dict[str, Any], date_str: str, natal_chart: Dict[str, Any], orb_max: float) -> TransitEvent:
    """Constrói um objeto TransitEvent a partir de um aspecto calculado."""
    transit_planet = aspect["transit_planet"]
    natal_planet = aspect["natal_planet"]
    aspect_key = aspect["aspect"]
    orb_deg = float(aspect.get("orb", 0.0))

    transitando_pt = planet_key_to_ptbr(transit_planet)
    alvo_pt = planet_key_to_ptbr(natal_planet)
    aspect_pt = aspect_to_ptbr(aspect_key)
    tags = get_event_tags(transit_planet, aspect_key)
    score = get_impact_score(transit_planet, aspect_key, natal_planet, orb_deg, orb_max)

    event_hash = hashlib.sha1(
        f"{date_str}:{transit_planet}:{natal_planet}:{aspect_key}:{round(orb_deg,2)}".encode("utf-8")
    ).hexdigest()

    date_start = f"{date_str}T00:00:00Z"
    date_peak = f"{date_str}T12:00:00Z"
    date_end = f"{date_str}T23:59:59Z"

    natal_cusps = natal_chart.get("houses", {}).get("cusps", [])
    natal_lon = float(natal_chart.get("planets", {}).get(natal_planet, {}).get("lon", 0.0))

    tag_base = tags[0] if tags else "foco"
    copy = TransitEventCopy(
        headline=f"{transitando_pt} em {aspect_pt} com {alvo_pt}",
        mecanica=f"Trânsito enfatiza {tag_base.lower()} em temas ligados a {alvo_pt}.",
        use_bem="Tendência a favorecer clareza e ação prática quando você organiza prioridades.",
        risco="Pede atenção a impulsos e excesso de carga; ajuste o ritmo com consistência.",
    )

    return TransitEvent(
        event_id=event_hash,
        date_range=TransitEventDateRange(start_utc=date_start, peak_utc=date_peak, end_utc=date_end),
        transitando=transitando_pt,
        alvo_tipo="PLANETA_NATAL",
        alvo=alvo_pt,
        aspecto=aspect_pt,
        orb_graus=round(orb_deg, 2),
        casa_ativada=get_house_for_lon(natal_cusps, natal_lon) if natal_cusps else None,
        tags=tags,
        severidade=get_severity_for_score(score),
        impact_score=score,
        copy=copy,
    )

def curate_daily_events(events: List[TransitEvent]) -> Dict[str, Any]:
    """Seleciona e organiza os eventos mais relevantes do dia."""
    if not events:
        return {"top_event": None, "trigger_event": None, "secondary_events": [], "summary": None}

    ordered = sorted(events, key=lambda item: item.impact_score, reverse=True)
    top_event = ordered[0]

    trigger_event = next(
        (item for item in ordered if item.transitando == "Marte" and item.impact_score >= 55),
        None,
    )
    if trigger_event is None and len(ordered) > 1:
        trigger_event = ordered[1]

    secondary_pool = [item for item in ordered[1:] if item != trigger_event]
    secondary_events = secondary_pool[:2]

    tags = top_event.tags or []
    tag = tags[0] if tags else "foco"
    summary = {
        "tom": f"Tendência a concentrar energia em {tag.lower()}.",
        "gatilho": f"{top_event.transitando} em {top_event.aspecto} com {top_event.alvo} pede atenção a prioridades.",
        "acao": "Aja com consistência e ajuste o ritmo conforme o contexto.",
    }

    return {
        "top_event": top_event,
        "trigger_event": trigger_event,
        "secondary_events": secondary_events,
        "summary": summary,
    }

def calculate_areas_activated(aspects: List[Dict[str, Any]], moon_phase: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calcula o nível de ativação de diferentes áreas da vida com base nos aspectos atuais."""
    base_score = 50.0
    orb_max_default = 6.0

    area_config = {
        "Emoções": {"planets": {"Moon", "Neptune", "Pluto"}},
        "Relações": {"planets": {"Venus", "Mars"}},
        "Trabalho": {"planets": {"Sun", "Saturn", "Jupiter"}},
        "Corpo": {"planets": {"Mars", "Saturn", "Sun"}},
    }

    scores: Dict[str, Dict[str, Any]] = {
        area: {"score": base_score, "top_aspect": None, "top_weight": 0.0}
        for area in area_config.keys()
    }

    aspect_weights = {"conjunction": 14, "opposition": 14, "square": 12, "trine": 9, "sextile": 7}
    supportive = {"trine", "sextile"}
    challenging = {"square", "opposition"}
    conjunction_positive = {"Venus", "Jupiter"}
    conjunction_negative = {"Mars", "Saturn", "Pluto"}

    for asp in aspects:
        aspect_type = asp.get("aspect")
        if aspect_type not in aspect_weights:
            continue
        orb = float(asp.get("orb", 0.0))
        weight = aspect_weights[aspect_type] * max(0.0, 1.0 - (orb / orb_max_default))

        sign = 0.0
        if aspect_type in supportive:
            sign = 1.0
        elif aspect_type in challenging:
            sign = -1.0
        elif aspect_type == "conjunction":
            planets = {asp.get("transit_planet"), asp.get("natal_planet")}
            if planets & conjunction_negative: sign = -0.5
            elif planets & conjunction_positive: sign = 0.5

        for area, config in area_config.items():
            if asp.get("transit_planet") in config["planets"] or asp.get("natal_planet") in config["planets"]:
                scores[area]["score"] += weight * sign
                if abs(weight * sign) > scores[area]["top_weight"]:
                    scores[area]["top_weight"] = abs(weight * sign)
                    scores[area]["top_aspect"] = asp

    if moon_phase in {"full_moon", "new_moon"}:
        scores["Emoções"]["score"] += 3

    items = []
    for area, data in scores.items():
        score = max(0, min(100, round(data["score"], 1)))
        level = "low" if score <= 34 else "medium" if score <= 59 else "high" if score <= 79 else "intense"
        items.append({"area": area, "level": level, "score": score, "reason": f"Top aspect: {data['top_aspect'].get('transit_planet')} {data['top_aspect'].get('aspect')} {data['top_aspect'].get('natal_planet')}." if data["top_aspect"] else "No strong aspects detected."})

    return items

def resolve_orb_max(orbes: Optional[Dict[str, float]], preferencias: Optional[PreferenciasPerfil]) -> float:
    """Resolve o orb máximo a ser utilizado nos cálculos."""
    if preferencias and preferencias.orb_max_deg is not None:
        return float(preferencias.orb_max_deg)
    if orbes:
        return max(float(value) for value in orbes.values())
    return PROFILE_DEFAULT_ORB_MAX

def apply_profile_defaults(aspectos_habilitados: Optional[List[str]], orbes: Optional[Dict[str, float]], preferencias: Optional[PreferenciasPerfil]) -> tuple[Optional[List[str]], Optional[Dict[str, float]], float, str]:
    """Aplica os valores padrão de perfil se necessário."""
    profile = preferencias.perfil if preferencias and preferencias.perfil else "custom" if preferencias else "padrao"
    orb_max = resolve_orb_max(orbes, preferencias)
    if profile == "padrao":
        if aspectos_habilitados is None: aspectos_habilitados = list(PROFILE_DEFAULT_ASPECTS)
        if orbes is None: orbes = {asp: PROFILE_DEFAULT_ORB_MAX for asp in aspectos_habilitados}
        orb_max = PROFILE_DEFAULT_ORB_MAX
    return aspectos_habilitados, orbes, orb_max, profile

def apply_solar_return_profile(preferencias: Optional[SolarReturnPreferencias]) -> tuple[Optional[List[str]], Optional[Dict[str, float]], float, str]:
    """Aplica o perfil de preferências para Revolução Solar."""
    if preferencias is None: perfil = "padrao"
    elif preferencias.perfil is None: perfil = "custom"
    else: perfil = preferencias.perfil

    aspectos_habilitados = preferencias.aspectos_habilitados if preferencias else None
    orbes = preferencias.orbes if preferencias else None
    orb_max = float(preferencias.orb_max_deg) if preferencias and preferencias.orb_max_deg is not None else resolve_orb_max(orbes, None)

    if perfil == "padrao":
        if aspectos_habilitados is None: aspectos_habilitados = list(PROFILE_DEFAULT_ASPECTS)
        if orbes is None: orbes = {asp: PROFILE_DEFAULT_ORB_MAX for asp in aspectos_habilitados}
        orb_max = PROFILE_DEFAULT_ORB_MAX
    return aspectos_habilitados, orbes, orb_max, perfil

def get_moon_phase_key(phase_angle_deg: float) -> str:
    """Retorna a chave da fase da lua (new_moon, waxing, full_moon, waning)."""
    a = phase_angle_deg % 360
    if a < 45 or a >= 315: return "new_moon"
    if 45 <= a < 135: return "waxing"
    if 135 <= a < 225: return "full_moon"
    return "waning"

def get_moon_phase_label_pt(phase_key: str) -> str:
    """Retorna o rótulo em português para a fase da lua."""
    labels = {
        "new_moon": "Nova",
        "waxing": "Crescente",
        "full_moon": "Cheia",
        "waning": "Minguante",
    }
    return labels.get(phase_key, phase_key)

def get_cosmic_weather_text(phase: str, sign: str) -> str:
    """Gera um texto aleatório porém consistente para o clima cósmico."""
    options = [
        "O dia tende a favorecer mais presença emocional e escolhas com calma. Ajustes pequenos podem ter efeito grande.",
        "Pode ser um dia de observação interna. Priorize o essencial e evite decidir no pico da emoção.",
        "A energia pode ficar mais intensa em alguns momentos. Pausas curtas e ritmo consistente ajudam.",
    ]
    return options[hash(phase + sign) % len(options)]

def apply_sign_localization(chart: Dict[str, Any], is_pt: bool) -> Dict[str, Any]:
    """Aplica a tradução dos signos no mapa natal/trânsitos."""
    planets = chart.get("planets", {})
    for planet in planets.values():
        sign = planet.get("sign")
        if not sign: continue
        sign_pt = sign_to_pt(sign)
        planet["sign_pt"] = sign_pt
        if is_pt:
            planet["sign"] = sign_pt
    return chart

def apply_moon_localization(payload: Dict[str, Any], is_pt: bool) -> Dict[str, Any]:
    """Aplica a tradução da lua no payload."""
    sign = payload.get("moon_sign")
    if sign:
        sign_pt = sign_to_pt(sign)
        payload["moon_sign_pt"] = sign_pt
        if is_pt:
            payload["moon_sign"] = sign_pt
            if "headline" in payload:
                payload["headline"] = payload["headline"].replace(sign, sign_pt)
    return payload

def build_daily_summary(phase: str, sign: str) -> Dict[str, str]:
    """
    Gera um resumo textual do clima astrológico do dia (Tom, Gatilho e Ação Sugerida).
    Leva em conta a fase lunar e o signo onde a Lua se encontra.
    """
    sign_pt = sign_to_ptbr(sign)
    templates = {
        "new_moon": {
            "tom": "Início de ciclo com foco em intenção e organização.",
            "gatilho": f"Tendência a priorizar decisões ligadas a {sign_pt}.",
            "acao": "Defina uma ação simples e mantenha o ritmo ao longo do dia.",
        },
        "waxing": {
            "tom": "Fase de avanço com energia de construção.",
            "gatilho": f"Tendência a buscar progresso em temas de {sign_pt}.",
            "acao": "Escolha uma meta prática e execute em etapas curtas.",
        },
        "full_moon": {
            "tom": "Pico de visibilidade e ajustes de equilíbrio.",
            "gatilho": f"Tendência a perceber resultados em assuntos de {sign_pt}.",
            "acao": "Revisite o que já foi iniciado e faça correções objetivas.",
        },
        "waning": {
            "tom": "Fase de depuração e reorganização.",
            "gatilho": f"Tendência a limpar excessos em temas de {sign_pt}.",
            "acao": "Finalize pendências e reduza ruídos antes de seguir.",
        },
    }
    return templates.get(phase, templates["waxing"])

def get_strength_from_score(score: float) -> str:
    """Converte um score numérico em um nível de força (low, medium, high)."""
    if score >= 70: return "high"
    if score >= 45: return "medium"
    return "low"

def get_icon_for_tags(tags: List[str]) -> str:
    """Retorna um emoji correspondente às tags fornecidas."""
    tag_map = {
        "trabalho": "💼", "carreira": "💼", "relacionamentos": "💞",
        "amor": "💞", "emoções": "🌙", "emocional": "🌙",
        "energia": "🔥", "corpo": "🔥", "foco": "🎯",
    }
    for tag in tags:
        key = tag.lower()
        if key in tag_map: return tag_map[key]
    return "✨"

def get_mercury_retrograde_alert(date_str: str, lat: float, lng: float, tz_offset: int) -> Optional[SystemAlert]:
    """Verifica e retorna um alerta se Mercúrio estiver retrógrado."""
    from services.time_utils import parse_date_yyyy_mm_dd
    y, m, d = parse_date_yyyy_mm_dd(date_str)
    chart = compute_transits(target_year=y, target_month=m, target_day=d, lat=lat, lng=lng, tz_offset_minutes=tz_offset)
    mercury = chart.get("planets", {}).get("Mercury")
    if not mercury or mercury.get("speed") is None:
        return None

    if mercury.get("retrograde"):
        return SystemAlert(
            id="mercury_retrograde",
            severity="medium",
            title="Mercúrio retrógrado",
            body="Mercúrio está em retrogradação. Revise comunicações e contratos com atenção.",
            technical={"mercury_speed": mercury.get("speed"), "mercury_lon": mercury.get("lon")},
        )
    return None
