import os
from typing import Dict, List, Optional, Tuple

from astro.utils import angle_diff

ASPECTS_LEGACY: Dict[str, dict] = {
    "conjunction": {"angle": 0, "orb": 6, "influence": "intense"},
    "opposition": {"angle": 180, "orb": 6, "influence": "challenging"},
    "square": {"angle": 90, "orb": 5, "influence": "challenging"},
    "trine": {"angle": 120, "orb": 5, "influence": "supportive"},
    "sextile": {"angle": 60, "orb": 4, "influence": "supportive"},
}

ASPECTS_MODERN: Dict[str, dict] = {
    "conjunction": {"angle": 0, "orb": 8, "influence": "intense"},
    "opposition": {"angle": 180, "orb": 8, "influence": "challenging"},
    "square": {"angle": 90, "orb": 6, "influence": "challenging"},
    "trine": {"angle": 120, "orb": 6, "influence": "supportive"},
    "sextile": {"angle": 60, "orb": 5, "influence": "supportive"},
    "quincunx": {"angle": 150, "orb": 3, "influence": "adjusting"},
    "semisextile": {"angle": 30, "orb": 2, "influence": "subtle"},
    "semisquare": {"angle": 45, "orb": 2, "influence": "challenging"},
    "sesquisquare": {"angle": 135, "orb": 2, "influence": "challenging"},
}

ASPECTS_STRICT: Dict[str, dict] = {
    "conjunction": {"angle": 0, "orb": 4, "influence": "intense"},
    "opposition": {"angle": 180, "orb": 4, "influence": "challenging"},
    "square": {"angle": 90, "orb": 4, "influence": "challenging"},
    "trine": {"angle": 120, "orb": 4, "influence": "supportive"},
    "sextile": {"angle": 60, "orb": 3, "influence": "supportive"},
}

ASPECTS_PROFILES: Dict[str, Dict[str, dict]] = {
    "legacy": ASPECTS_LEGACY,
    "modern": ASPECTS_MODERN,
    "strict": ASPECTS_STRICT,
}

ASPECTS = ASPECTS_PROFILES["legacy"]


def resolve_aspects_profile(profile: Optional[str]) -> Tuple[str, Dict[str, dict]]:
    key = (profile or "").strip().lower() or "legacy"
    aspects = ASPECTS_PROFILES.get(key)
    if aspects is None:
        key = "legacy"
        aspects = ASPECTS_PROFILES[key]
    return key, aspects


def get_aspects_profile() -> Tuple[str, Dict[str, dict]]:
    return resolve_aspects_profile(os.getenv("ASPECTS_PROFILE"))

ASPECT_ALIASES = {
    "conj": "conjunction",
    "conjunction": "conjunction",
    "opos": "opposition",
    "opposition": "opposition",
    "quad": "square",
    "square": "square",
    "tri": "trine",
    "trine": "trine",
    "sext": "sextile",
    "sextile": "sextile",
}

ASPECT_ABBREVIATIONS = {
    "conjunction": "conj",
    "opposition": "opos",
    "square": "quad",
    "trine": "tri",
    "sextile": "sext",
}


def _normalize_aspect_key(value: str) -> Optional[str]:
    if not value:
        return None
    key = value.strip().lower()
    return ASPECT_ALIASES.get(key)


def resolve_aspects_config(
    aspectos_habilitados: Optional[List[str]] = None,
    orbes: Optional[Dict[str, float]] = None,
) -> Tuple[Dict[str, dict], List[str], Dict[str, float]]:
    aspects = {key: {**info} for key, info in ASPECTS.items()}

    if orbes:
        for aspect_key, orb_value in orbes.items():
            normalized = _normalize_aspect_key(aspect_key)
            if normalized and normalized in aspects:
                aspects[normalized] = {**aspects[normalized], "orb": float(orb_value)}

    if aspectos_habilitados is not None:
        selected: List[str] = []
        seen = set()
        for aspect_key in aspectos_habilitados:
            normalized = _normalize_aspect_key(aspect_key)
            if normalized and normalized in aspects and normalized not in seen:
                selected.append(normalized)
                seen.add(normalized)
        aspects = {key: aspects[key] for key in selected}

    aspectos_usados = [ASPECT_ABBREVIATIONS.get(key, key) for key in aspects.keys()]
    orbes_usados = {
        ASPECT_ABBREVIATIONS.get(key, key): float(info["orb"]) for key, info in aspects.items()
    }
    return aspects, aspectos_usados, orbes_usados


def resolve_aspects(
    aspects_profile: Optional[str] = None,
    aspectos_habilitados: Optional[List[str]] = None,
    orbes: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, object]]:
    profile = (aspects_profile or os.getenv("ASPECTS_PROFILE", "legacy")).lower()
    base = ASPECTS_PROFILES.get(profile, ASPECTS_LEGACY)
    aspects = {name: info.copy() for name, info in base.items()}

    if aspectos_habilitados:
        enabled = {aspect for aspect in aspectos_habilitados if aspect in aspects}
        aspects = {name: info for name, info in aspects.items() if name in enabled}

    if orbes:
        for aspect_name, orb in orbes.items():
            if aspect_name in aspects:
                aspects[aspect_name]["orb"] = float(orb)

    return aspects


def compute_transit_aspects(
    transit_planets: Dict[str, dict],
    natal_planets: Dict[str, dict],
    aspects: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    aspects_found = []
    if aspects is None:
        _, aspects = get_aspects_profile()
    
    for t_name, t_data in transit_planets.items():
        t_lon = t_data["lon"]
        
        for n_name, n_data in natal_planets.items():
            n_lon = n_data["lon"]
            
            separation = angle_diff(t_lon, n_lon)
            
            for aspect_name, aspect_info in aspects.items():
                target_angle = aspect_info["angle"]
                max_orb = aspect_info["orb"]
                
                orb = abs(separation - target_angle)
                
                if orb <= max_orb:
                    aspects_found.append({
                        "transit_planet": t_name,
                        "natal_planet": n_name,
                        "aspect": aspect_name,
                        "exact_angle": target_angle,
                        "actual_angle": round(separation, 4),
                        "orb": round(orb, 4),
                        "influence": aspect_info["influence"],
                    })
    
    aspects_found.sort(key=lambda x: x["orb"])
    
    return aspects_found
