from typing import List, Dict, Optional, Tuple
from astro.utils import angle_diff

ASPECTS = {
    "conjunction": {"angle": 0, "orb": 6, "influence": "intense"},
    "opposition": {"angle": 180, "orb": 6, "influence": "challenging"},
    "square": {"angle": 90, "orb": 5, "influence": "challenging"},
    "trine": {"angle": 120, "orb": 5, "influence": "supportive"},
    "sextile": {"angle": 60, "orb": 4, "influence": "supportive"},
}

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


def compute_transit_aspects(
    transit_planets: Dict[str, dict],
    natal_planets: Dict[str, dict],
    aspects: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    aspects_found = []
    aspects = aspects or ASPECTS
    
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
