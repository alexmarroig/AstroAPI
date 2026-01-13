from __future__ import annotations

from typing import Any, Dict, List

from astro.utils import ZODIAC_SIGNS, ZODIAC_SIGNS_PT

PLANET_PTBR = {
    "Sun": "Sol",
    "Moon": "Lua",
    "Mercury": "Mercúrio",
    "Venus": "Vênus",
    "Mars": "Marte",
    "Jupiter": "Júpiter",
    "Saturn": "Saturno",
    "Uranus": "Urano",
    "Neptune": "Netuno",
    "Pluto": "Plutão",
}

ASPECT_PTBR = {
    "conjunction": "Conjunção",
    "opposition": "Oposição",
    "square": "Quadratura",
    "trine": "Trígono",
    "sextile": "Sextil",
}

SIGN_LOOKUP = {sign.lower(): pt for sign, pt in zip(ZODIAC_SIGNS, ZODIAC_SIGNS_PT)}
SIGN_LOOKUP.update({pt.lower(): pt for pt in ZODIAC_SIGNS_PT})
SIGN_LOOKUP.update(
    {
        "ari": "Áries",
        "aries": "Áries",
        "tau": "Touro",
        "taurus": "Touro",
        "gem": "Gêmeos",
        "gemini": "Gêmeos",
        "can": "Câncer",
        "cancer": "Câncer",
        "leo": "Leão",
        "vir": "Virgem",
        "virgo": "Virgem",
        "lib": "Libra",
        "libra": "Libra",
        "sco": "Escorpião",
        "scorpio": "Escorpião",
        "sag": "Sagitário",
        "sagittarius": "Sagitário",
        "cap": "Capricórnio",
        "capricorn": "Capricórnio",
        "aqu": "Aquário",
        "aquarius": "Aquário",
        "pis": "Peixes",
        "pisces": "Peixes",
    }
)


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def normalize_longitude(lon: float) -> float:
    return lon % 360.0


def planet_key_to_ptbr(name: str) -> str:
    return PLANET_PTBR.get(safe_str(name), safe_str(name))


def sign_to_ptbr(sign: str) -> str:
    key = safe_str(sign).strip().lower()
    return SIGN_LOOKUP.get(key, safe_str(sign))


def aspect_to_ptbr(aspect: str) -> str:
    key = safe_str(aspect).strip().lower()
    return ASPECT_PTBR.get(key, safe_str(aspect))


def house_theme_ptbr(house: int) -> str:
    themes = {
        1: "Identidade",
        2: "Finanças/valores",
        3: "Comunicação",
        4: "Família e base",
        5: "Criatividade",
        6: "Rotina e saúde",
        7: "Relacionamentos",
        8: "Transformações",
        9: "Visão e estudos",
        10: "Carreira",
        11: "Amizades e redes",
        12: "Inconsciente",
    }
    return themes.get(house, "Tema geral")


def format_degree_ptbr(degrees: float) -> str:
    deg_int = int(degrees)
    minutes = int(round((degrees - deg_int) * 60))
    if minutes == 60:
        minutes = 0
        deg_int += 1
    return f"{deg_int}°{minutes:02d}'"


def format_position_ptbr(degrees: float, sign: str) -> str:
    sign_pt = sign_to_ptbr(sign)
    return f"{format_degree_ptbr(degrees)} {sign_pt}"


def build_planets_ptbr(planets: Dict[str, dict]) -> Dict[str, dict]:
    translated: Dict[str, dict] = {}
    for key, data in planets.items():
        name_pt = planet_key_to_ptbr(key)
        sign_pt = sign_to_ptbr(data.get("sign", ""))
        deg_in_sign = float(data.get("deg_in_sign", 0.0))
        translated[name_pt] = {
            **data,
            "nome_ptbr": name_pt,
            "signo_ptbr": sign_pt,
            "grau_formatado_ptbr": format_position_ptbr(deg_in_sign, sign_pt),
            "retrogrado_ptbr": "Retrógrado" if data.get("retrograde") else "Direto",
        }
    return translated


def build_houses_ptbr(houses: dict) -> dict:
    cusps = houses.get("cusps", [])
    asc = float(houses.get("asc", 0.0))
    mc = float(houses.get("mc", 0.0))
    return {
        "system_ptbr": houses.get("system"),
        "asc_ptbr": format_position_ptbr(asc % 30, sign_for_longitude(asc)),
        "mc_ptbr": format_position_ptbr(mc % 30, sign_for_longitude(mc)),
        "cusps_ptbr": [
            f"Casa {idx + 1}: {format_position_ptbr(float(cusp) % 30, sign_for_longitude(float(cusp)))}"
            for idx, cusp in enumerate(cusps)
        ],
    }


def build_aspects_ptbr(aspects: List[dict]) -> List[dict]:
    translated: List[dict] = []
    for asp in aspects:
        translated.append(
            {
                **asp,
                "tipo_ptbr": aspect_to_ptbr(asp.get("aspect")),
                "corpo1_ptbr": planet_key_to_ptbr(asp.get("transit_planet")),
                "corpo2_ptbr": planet_key_to_ptbr(asp.get("natal_planet")),
                "orb_formatado_ptbr": format_degree_ptbr(float(asp.get("orb", 0.0))),
            }
        )
    return translated


def sign_for_longitude(lon: float) -> str:
    lon_norm = normalize_longitude(lon)
    idx = int(lon_norm // 30) % 12
    return ZODIAC_SIGNS[idx]
