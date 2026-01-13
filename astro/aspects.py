import os
from typing import Dict, List, Optional, Tuple

from astro.utils import angle_diff

ASPECTS_PROFILES: Dict[str, Dict[str, dict]] = {
    "legacy": {
        "conjunction": {"angle": 0, "orb": 6, "influence": "intense"},
        "opposition": {"angle": 180, "orb": 6, "influence": "challenging"},
        "square": {"angle": 90, "orb": 5, "influence": "challenging"},
        "trine": {"angle": 120, "orb": 5, "influence": "supportive"},
        "sextile": {"angle": 60, "orb": 4, "influence": "supportive"},
    },
    "modern": {
        "conjunction": {"angle": 0, "orb": 8, "influence": "intense"},
        "opposition": {"angle": 180, "orb": 8, "influence": "challenging"},
        "square": {"angle": 90, "orb": 6, "influence": "challenging"},
        "trine": {"angle": 120, "orb": 6, "influence": "supportive"},
        "sextile": {"angle": 60, "orb": 5, "influence": "supportive"},
        "quincunx": {"angle": 150, "orb": 3, "influence": "adjusting"},
        "semisextile": {"angle": 30, "orb": 2, "influence": "subtle"},
        "semisquare": {"angle": 45, "orb": 2, "influence": "challenging"},
        "sesquisquare": {"angle": 135, "orb": 2, "influence": "challenging"},
    },
    "strict": {
        "conjunction": {"angle": 0, "orb": 4, "influence": "intense"},
        "opposition": {"angle": 180, "orb": 4, "influence": "challenging"},
        "square": {"angle": 90, "orb": 4, "influence": "challenging"},
        "trine": {"angle": 120, "orb": 4, "influence": "supportive"},
        "sextile": {"angle": 60, "orb": 3, "influence": "supportive"},
    },
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
