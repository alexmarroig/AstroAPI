from __future__ import annotations

import asyncio
import calendar
import logging
import os
from datetime import date as dt_date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request
from openai import OpenAI
from pydantic import BaseModel

from .common import get_auth
from astro.ephemeris import compute_chart, compute_moon_only, solar_return_datetime
from astro.i18n_ptbr import aspect_to_ptbr, planet_key_to_ptbr, sign_to_ptbr
from core.cache import cache
from services.astro_logic import (
    build_daily_summary,
    get_moon_phase_key,
    get_moon_phase_label_pt,
)
from services.lunations import calculate_lunation
from services.progressions import calculate_secondary_progressions
from services.time_utils import get_tz_offset_minutes

router = APIRouter()
logger = logging.getLogger("astro-api")

DAILY_ANALYSIS_TTL = 60 * 60
LUNAR_CALENDAR_TTL = 24 * 60 * 60
SOLAR_RETURN_TTL = 24 * 60 * 60


class AstralOracleContext(BaseModel):
    date: Optional[str] = None
    sunSign: Optional[str] = None
    moonSign: Optional[str] = None
    risingSign: Optional[str] = None
    userTz: Optional[str] = None


class AstralOracleRequest(BaseModel):
    userId: Optional[str] = None
    question: Optional[str] = None
    context: Optional[AstralOracleContext] = None


def _log_error(message: str, user_id: str, request_id: Optional[str]) -> None:
    logger.error(
        message,
        extra={"user_id": user_id, "request_id": request_id},
        exc_info=True,
    )


def _normalize_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Data inválida. Use o formato YYYY-MM-DD.") from exc


def _parse_int(value: Optional[str], field: str, minimum: int, maximum: int) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} deve ser um número válido.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field} deve estar entre {minimum} e {maximum}.")
    return parsed


def _parse_float(value: Optional[str], field: str, minimum: float, maximum: float) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} deve ser um número válido.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field} deve estar entre {minimum} e {maximum}.")
    return parsed


def _daily_text_prefix(target_date: dt_date) -> str:
    today = dt_date.today()
    if target_date == today:
        return "Hoje"
    if target_date > today:
        return "Nos próximos passos do dia"
    return "No ritmo desse dia"


def _build_daily_section(phase_key: str, sign: str) -> Dict[str, str]:
    templates = {
        "new_moon": {
            "climate": "Clima de recomeço, como se o céu sussurrasse novas intenções.",
            "emotions": "Emoções pedem silêncio e escolhas mais gentis.",
            "relationships": "Relações florescem quando há escuta e simplicidade.",
            "work": "Trabalho ganha clareza com metas pequenas e firmes.",
            "body": "O corpo pede pausa breve para reorganizar energia.",
        },
        "waxing": {
            "climate": "Clima de construção, o céu favorece passos consistentes.",
            "emotions": "Emoções querem movimento, sem pressa.",
            "relationships": "Relações evoluem com presença e conversas diretas.",
            "work": "Trabalho pede foco em progresso gradual.",
            "body": "O corpo responde bem a rotinas leves e atentas.",
        },
        "full_moon": {
            "climate": "Clima de intensidade e iluminação emocional.",
            "emotions": "Emoções ficam evidentes, pedindo verdade e cuidado.",
            "relationships": "Relações mostram o que precisa de ajuste.",
            "work": "Trabalho se beneficia de revisão de prioridades.",
            "body": "O corpo pede respiração profunda e ritmo mais suave.",
        },
        "waning": {
            "climate": "Clima de limpeza, o céu pede desapego prático.",
            "emotions": "Emoções querem fechar ciclos e aliviar excessos.",
            "relationships": "Relações prosperam com acordos e limites claros.",
            "work": "Trabalho favorece conclusão e organização.",
            "body": "O corpo pede descanso consciente e hidratação.",
        },
    }
    payload = templates.get(phase_key, templates["waxing"]).copy()
    payload["climate"] = f"{payload['climate']} A Lua percorre {sign_to_ptbr(sign)}."
    return payload


def _build_upcoming_days(start_date: dt_date, tz_offset_minutes: int) -> List[Dict[str, str]]:
    days = []
    for offset in range(1, 4):
        current = start_date + timedelta(days=offset)
        moon = compute_moon_only(current.strftime("%Y-%m-%d"), tz_offset_minutes=tz_offset_minutes)
        phase_key = get_moon_phase_key(moon["phase_angle_deg"])
        phase_label = get_moon_phase_label_pt(phase_key)
        sign = moon["moon_sign"]
        summary = build_daily_summary(phase_key, sign)
        days.append({
            "date": current.isoformat(),
            "mood": f"Lua {phase_label} em {sign_to_ptbr(sign)}",
            "summary": summary["tom"],
        })
    return days


def _build_technical_aspects(phase_key: str, sign: str, moon_deg: float | None) -> List[Dict[str, str]]:
    aspects = [
        {
            "title": "Fase lunar",
            "detail": f"Lua {get_moon_phase_label_pt(phase_key)} iluminando decisões.",
        },
        {
            "title": "Signo lunar",
            "detail": f"A Lua transita {sign_to_ptbr(sign)}, afinando percepções.",
        },
    ]
    if moon_deg is not None:
        aspects.append({
            "title": "Grau lunar",
            "detail": f"A Lua percorre o grau {round(moon_deg, 1)} de {sign_to_ptbr(sign)}.",
        })
    return aspects


@router.get("/api/daily-analysis/{date}")
async def daily_analysis(date: str, request: Request, auth=Depends(get_auth)):
    user_id = auth["user_id"]
    cache_key = f"daily-analysis:{user_id}:{date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        date_dt = _normalize_date(date)
        target_date = date_dt.date()
        tz_offset = get_tz_offset_minutes(date_dt, "UTC", 0)
        moon = compute_moon_only(date, tz_offset_minutes=tz_offset)
        phase_key = get_moon_phase_key(moon["phase_angle_deg"])
        phase_label = get_moon_phase_label_pt(phase_key)
        sign = moon["moon_sign"]

        summary = build_daily_summary(phase_key, sign)
        prefix = _daily_text_prefix(target_date)
        sections = _build_daily_section(phase_key, sign)

        payload = {
            "success": True,
            "date": date,
            "mood": f"{prefix}, a Lua {phase_label.lower()} inspira {summary['tom'].lower()}",
            "summary": f"{prefix}, {summary['gatilho']} {summary['acao']}",
            "climate": sections["climate"],
            "emotions": sections["emotions"],
            "relationships": sections["relationships"],
            "work": sections["work"],
            "body": sections["body"],
            "lunarPhase": {
                "type": phase_key,
                "sign": sign_to_ptbr(sign),
                "name": f"Lua {phase_label}",
            },
            "upcomingDays": _build_upcoming_days(target_date, tz_offset),
            "technicalAspects": _build_technical_aspects(phase_key, sign, moon.get("deg_in_sign")),
        }
        cache.set(cache_key, payload, ttl_seconds=DAILY_ANALYSIS_TTL)
        return payload
    except Exception:
        _log_error("daily_analysis_error", user_id, getattr(request.state, "request_id", None))
        return {
            "success": False,
            "message": "Algo deu errado com os astros, tente novamente em instantes.",
        }


def _match_quick_answer(question: str) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    q = question.lower()
    if any(term in q for term in ["como é meu dia", "como esta meu dia", "meu dia hoje", "como vai meu dia"]):
        return (
            "O dia pede calma e escolhas simples. Respire fundo, avance em pequenos passos e celebre cada conquista.",
            "dia",
            0.92,
        )
    if any(term in q for term in ["dicas de trabalho", "trabalho", "carreira"]):
        return (
            "No trabalho, organize prioridades e preserve sua energia. O céu favorece foco e entregas bem alinhadas.",
            "trabalho",
            0.9,
        )
    if any(term in q for term in ["relacionamentos", "amor", "parceria"]):
        return (
            "Relações pedem presença e ternura. Ouça antes de responder e deixe espaço para gestos simples.",
            "relacionamentos",
            0.9,
        )
    if any(term in q for term in ["equilíbrio pessoal", "equilibrio pessoal", "autocuidado"]):
        return (
            "Seu equilíbrio cresce quando você respeita o ritmo do corpo. Pausas curtas e silêncio restauram.",
            "equilibrio",
            0.88,
        )
    return None, None, None


async def _call_llm(messages: List[Dict[str, str]], max_tokens: int, api_key: str) -> str:
    client = OpenAI(api_key=api_key)
    loop = asyncio.get_running_loop()

    def _request() -> str:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content

    return await loop.run_in_executor(None, _request)


@router.post("/api/chat/astral-oracle")
async def astral_oracle(body: AstralOracleRequest, request: Request, auth=Depends(get_auth)):
    user_id = auth["user_id"]
    if not body.question or not body.context:
        return {
            "success": False,
            "answer": "Envie sua pergunta e um contexto astrológico para abrir o Oráculo.",
            "theme": "oraculo",
            "confidence": 0.1,
        }

    quick_answer, theme, confidence = _match_quick_answer(body.question)
    if quick_answer:
        return {
            "success": True,
            "answer": quick_answer,
            "theme": theme,
            "confidence": confidence,
        }

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _log_error("astral_oracle_missing_key", user_id, getattr(request.state, "request_id", None))
        return {
            "success": False,
            "answer": "Desculpe, o Oráculo está contemplando o cosmos. Tente novamente em alguns momentos.",
            "theme": "oraculo",
            "confidence": 0.2,
        }

    context = body.context
    context_text = (
        f"Data: {context.date or 'não informada'}. "
        f"Sol: {context.sunSign or 'não informado'}. "
        f"Lua: {context.moonSign or 'não informada'}. "
        f"Ascendente: {context.risingSign or 'não informado'}. "
        f"Fuso: {context.userTz or 'não informado'}."
    )
    messages = [
        {"role": "system", "content": "Você é um oráculo astral poético e prático. Responda em português."},
        {"role": "user", "content": f"Contexto astrológico: {context_text}"},
        {"role": "user", "content": f"Pergunta: {body.question}"},
    ]

    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS_PAID", "1100"))
    for attempt in range(2):
        try:
            answer = await asyncio.wait_for(_call_llm(messages, max_tokens, api_key), timeout=5)
            return {
                "success": True,
                "answer": answer,
                "theme": "oraculo",
                "confidence": 0.6,
            }
        except asyncio.TimeoutError:
            _log_error("astral_oracle_timeout", user_id, getattr(request.state, "request_id", None))
        except Exception:
            _log_error("astral_oracle_error", user_id, getattr(request.state, "request_id", None))

    return {
        "success": False,
        "answer": "Desculpe, o Oráculo está contemplando o cosmos. Tente novamente em alguns momentos.",
        "theme": "oraculo",
        "confidence": 0.2,
    }


@router.get("/api/solar-return")
async def solar_return_api(
    request: Request,
    natal_year: Optional[str] = Query(None),
    natal_month: Optional[str] = Query(None),
    natal_day: Optional[str] = Query(None),
    natal_hour: Optional[str] = Query(None),
    natal_minute: Optional[str] = Query(None),
    natal_second: Optional[str] = Query(None),
    target_year: Optional[str] = Query(None),
    lat: Optional[str] = Query(None),
    lng: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    user_id = auth["user_id"]
    try:
        parsed_year = _parse_int(target_year, "Ano alvo", 1800, 2100) or datetime.utcnow().year
        natal_year_i = _parse_int(natal_year, "Ano natal", 1800, 2100)
        natal_month_i = _parse_int(natal_month, "Mês natal", 1, 12)
        natal_day_i = _parse_int(natal_day, "Dia natal", 1, 31)
        natal_hour_i = _parse_int(natal_hour, "Hora natal", 0, 23)
        natal_minute_i = _parse_int(natal_minute, "Minuto natal", 0, 59) or 0
        natal_second_i = _parse_int(natal_second, "Segundo natal", 0, 59) or 0
        lat_f = _parse_float(lat, "Latitude", -89.9999, 89.9999)
        lng_f = _parse_float(lng, "Longitude", -180, 180)
    except ValueError as exc:
        return {
            "success": False,
            "message": str(exc),
        }

    if not all([natal_year_i, natal_month_i, natal_day_i, natal_hour_i is not None, lat_f is not None, lng_f is not None, timezone]):
        return {
            "success": False,
            "message": "Dados insuficientes para calcular sua revolução solar.",
        }

    cache_key = f"solar-return:{user_id}:{parsed_year}:{lat_f}:{lng_f}:{timezone}:{natal_year_i}-{natal_month_i}-{natal_day_i}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        natal_dt = datetime(
            natal_year_i,
            natal_month_i,
            natal_day_i,
            natal_hour_i,
            natal_minute_i,
            natal_second_i,
        )
        tz_offset = get_tz_offset_minutes(natal_dt, timezone, None)
        sr_utc = solar_return_datetime(natal_dt, parsed_year, tz_offset)
        sr_local = sr_utc + timedelta(minutes=tz_offset)
        chart = compute_chart(
            sr_local.year,
            sr_local.month,
            sr_local.day,
            sr_local.hour,
            sr_local.minute,
            sr_local.second,
            lat_f,
            lng_f,
            tz_offset,
            house_system="P",
            zodiac_type="tropical",
            ayanamsa=None,
        )

        positions = []
        for name, data in chart.get("planets", {}).items():
            sign = data.get("sign")
            deg = data.get("deg_in_sign")
            if sign is None or deg is None:
                continue
            positions.append({
                "planet": name,
                "planet_pt": planet_key_to_ptbr(name),
                "sign": sign,
                "sign_pt": sign_to_ptbr(sign),
                "deg_in_sign": round(float(deg), 2),
            })

        aspects = []
        planets = chart.get("planets", {})
        for t_name, t_data in planets.items():
            for n_name, n_data in planets.items():
                if t_name == n_name:
                    continue
                t_lon = float(t_data.get("lon", 0.0))
                n_lon = float(n_data.get("lon", 0.0))
                separation = abs((t_lon - n_lon + 180) % 360 - 180)
                if separation <= 6:
                    aspects.append({
                        "transit_planet": planet_key_to_ptbr(t_name),
                        "natal_planet": planet_key_to_ptbr(n_name),
                        "aspect": aspect_to_ptbr("conjunction"),
                        "orb": round(separation, 2),
                    })
        aspects = sorted(aspects, key=lambda item: item["orb"])[:5]

        themes = [
            "Revisitar intenções antigas para abrir espaço ao novo.",
            "Aprofundar vínculos com escolhas conscientes.",
            "Cultivar coragem para mudanças graduais.",
        ]

        pt_months = [
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ]
        monthly_forecast = []
        for idx, month_name in enumerate(pt_months, start=1):
            monthly_forecast.append({
                "month": idx,
                "pt_month": month_name,
                "energy": "energia de construção e alinhamento interior.",
                "focus": "foco em escolhas práticas e constância.",
            })

        payload = {
            "success": True,
            "solarReturnDate": sr_local.date().isoformat(),
            "solarReturnYear": parsed_year,
            "summary": "Um ano de ajustes gentis, onde clareza e presença sustentam cada decisão.",
            "keyThemes": themes,
            "chart": {
                "positions": positions,
                "aspects": aspects,
            },
            "monthlyForecast": monthly_forecast,
        }
        cache.set(cache_key, payload, ttl_seconds=SOLAR_RETURN_TTL)
        return payload
    except Exception:
        _log_error("solar_return_api_error", user_id, getattr(request.state, "request_id", None))
        return {
            "success": False,
            "message": "Não foi possível calcular sua revolução solar agora. Tente novamente em instantes.",
        }


@router.get("/api/lunar-calendar")
async def lunar_calendar(
    request: Request,
    month: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    user_id = auth["user_id"]
    today = dt_date.today()
    try:
        target_month = _parse_int(month, "Mês", 1, 12) or today.month
        target_year = _parse_int(year, "Ano", 1800, 2100) or today.year
    except ValueError as exc:
        return {
            "success": False,
            "message": str(exc),
        }
    cache_key = f"lunar-calendar:{user_id}:{target_year}:{target_month}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        _, days_in_month = calendar.monthrange(target_year, target_month)
        phases: List[Dict[str, Any]] = []
        seen_types = set()
        phase_map = {
            "new": ("new_moon", "Lua Nova"),
            "full": ("full_moon", "Lua Cheia"),
            "first_quarter": ("first_quarter", "Quarto Crescente"),
            "last_quarter": ("last_quarter", "Quarto Minguante"),
        }
        interpretations = {
            "new_moon": "Tempo de plantar desejos e cuidar da direção que você quer seguir.",
            "full_moon": "Tempo de enxergar com clareza e honrar o que precisa florescer.",
            "first_quarter": "Tempo de agir com coragem e ajustar o caminho.",
            "last_quarter": "Tempo de desapegar do que pesa e reorganizar prioridades.",
        }

        for day in range(1, days_in_month + 1):
            date_obj = datetime(target_year, target_month, day)
            lunation = calculate_lunation(date_obj, 0, None)
            phase_key = lunation.phase
            if phase_key in phase_map and phase_key not in seen_types:
                phase_type, phase_name = phase_map[phase_key]
                seen_types.add(phase_key)
                phases.append({
                    "date": lunation.date,
                    "type": phase_type,
                    "pt_name": phase_name,
                    "sign": lunation.moon_sign,
                    "pt_sign": lunation.moon_sign_pt,
                    "interpretation": interpretations[phase_type],
                })

        payload = {
            "success": True,
            "month": target_month,
            "pt_month": [
                "janeiro",
                "fevereiro",
                "março",
                "abril",
                "maio",
                "junho",
                "julho",
                "agosto",
                "setembro",
                "outubro",
                "novembro",
                "dezembro",
            ][target_month - 1],
            "year": target_year,
            "phases": phases,
        }
        cache.set(cache_key, payload, ttl_seconds=LUNAR_CALENDAR_TTL)
        return payload
    except Exception:
        _log_error("lunar_calendar_error", user_id, getattr(request.state, "request_id", None))
        return {
            "success": False,
            "message": "Não conseguimos ler o calendário lunar agora. Tente novamente em instantes.",
        }


@router.get("/api/secondary-progressions")
async def secondary_progressions(
    request: Request,
    natal_year: Optional[str] = Query(None),
    natal_month: Optional[str] = Query(None),
    natal_day: Optional[str] = Query(None),
    natal_hour: Optional[str] = Query(None),
    natal_minute: Optional[str] = Query(None),
    natal_second: Optional[str] = Query(None),
    lat: Optional[str] = Query(None),
    lng: Optional[str] = Query(None),
    timezone: Optional[str] = Query(None),
    auth=Depends(get_auth),
):
    user_id = auth["user_id"]
    try:
        natal_year_i = _parse_int(natal_year, "Ano natal", 1800, 2100)
        natal_month_i = _parse_int(natal_month, "Mês natal", 1, 12)
        natal_day_i = _parse_int(natal_day, "Dia natal", 1, 31)
        natal_hour_i = _parse_int(natal_hour, "Hora natal", 0, 23)
        natal_minute_i = _parse_int(natal_minute, "Minuto natal", 0, 59) or 0
        natal_second_i = _parse_int(natal_second, "Segundo natal", 0, 59) or 0
        lat_f = _parse_float(lat, "Latitude", -89.9999, 89.9999)
        lng_f = _parse_float(lng, "Longitude", -180, 180)
    except ValueError as exc:
        return {
            "success": False,
            "message": str(exc),
        }

    if not all([natal_year_i, natal_month_i, natal_day_i, lat_f is not None, lng_f is not None, timezone]):
        return {
            "success": False,
            "message": "Suas progressões ainda não estão disponíveis. Complete seus dados natais.",
        }

    try:
        hour = natal_hour_i if natal_hour_i is not None else 12
        natal_dt = datetime(natal_year_i, natal_month_i, natal_day_i, hour, natal_minute_i, natal_second_i)
        tz_offset = get_tz_offset_minutes(natal_dt, timezone, None)
        today = datetime.utcnow()
        result = calculate_secondary_progressions(
            natal_dt=natal_dt,
            target_date=today,
            lat=lat_f,
            lng=lng_f,
            tz_offset_minutes=tz_offset,
            house_system="P",
            zodiac_type="tropical",
            ayanamsa=None,
        )
        chart = result.chart.get("planets", {})
        progressed_chart = []
        for name, data in chart.items():
            sign = data.get("sign")
            if not sign:
                continue
            sign_pt = sign_to_ptbr(sign)
            progressed_chart.append({
                "planet": name,
                "sign": sign,
                "pt_sign": sign_pt,
            })

        payload = {
            "success": True,
            "progressedChart": progressed_chart,
            "currentPhase": "integração",
            "pt_phase": "integração",
            "timing": "Período de transformação interna em andamento.",
        }
        return payload
    except Exception:
        _log_error("secondary_progressions_error", user_id, getattr(request.state, "request_id", None))
        return {
            "success": False,
            "message": "Não foi possível calcular suas progressões agora. Tente novamente em instantes.",
        }
