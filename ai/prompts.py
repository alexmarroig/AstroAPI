from typing import Any, Optional

SYSTEM_PROMPT = """You are a thoughtful and insightful astrologer providing cosmic guidance. Follow these guidelines strictly:

TONE AND APPROACH:
- Maintain a calm, supportive, and reflective tone
- Use non-deterministic language (e.g., "may," "could," "tends to," "often")
- Never make concrete predictions or guarantee specific outcomes
- Present astrology as a tool for self-reflection, not fate

CONTENT RESTRICTIONS:
- No fear-based or alarming language
- No medical, legal, or financial advice
- Avoid suggesting that planetary positions cause events directly
- Present 2-3 plausible manifestations when symbolism is ambiguous

FORMAT:
- Use concise sections with clear headers
- Use bullet points for key insights
- Avoid astrological glyphs in the main output (use planet/sign names instead)
- Keep responses focused and digestible

INTERPRETATION STYLE:
- Frame challenges as opportunities for growth
- Emphasize free will and personal agency
- Connect cosmic patterns to inner psychological experiences
- Suggest constructive ways to work with energies"""

MAX_TEXT_FIELD_LENGTH = 180
MAX_PLANETS_PER_SECTION = 15
MAX_ASPECTS = 10

LANGUAGE_MAP = {
    "pt": "Portuguese (Brazil)",
    "pt-br": "Portuguese (Brazil)",
    "pt_br": "Portuguese (Brazil)",
    "en": "English",
    "en-us": "English",
    "english": "English",
    "es": "Spanish",
    "spanish": "Spanish",
}

DEFAULT_LANGUAGE = "Portuguese (Brazil)"
DEFAULT_TONE = "calm, supportive, and reflective"


def _truncate_text(value: Any, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str:
    if not isinstance(value, str):
        return "Unknown"
    value = value.strip()
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _to_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _to_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _normalize_language(language: Optional[str]) -> str:
    if not isinstance(language, str) or not language.strip():
        return DEFAULT_LANGUAGE
    normalized = language.strip().lower()
    return LANGUAGE_MAP.get(normalized, DEFAULT_LANGUAGE)


def _normalize_tone(tone: Optional[str]) -> str:
    if not isinstance(tone, str) or not tone.strip():
        return DEFAULT_TONE
    return _truncate_text(tone, max_length=80)


def _format_planet_line(planet: Any, data: Any) -> str:
    pdata = _to_dict(data)
    sign = _truncate_text(pdata.get("sign", "Unknown"), max_length=40)

    degree = pdata.get("deg_in_sign", 0)
    degree_value = float(degree) if isinstance(degree, (int, float)) else 0.0

    return f"  - {_truncate_text(planet, max_length=20)}: {sign} ({degree_value:.1f})"


def build_cosmic_chat_messages(
    user_question: str,
    astro_payload: dict,
    tone: Optional[str] = None,
    language: str = "English"
) -> list:
    normalized_tone = _normalize_tone(tone)
    normalized_language = _normalize_language(language)

    system_content = (
        f"{SYSTEM_PROMPT}"
        f"\n\nADDITIONAL TONE: Respond in a {normalized_tone} manner."
        f"\n\nLANGUAGE: Respond entirely in {normalized_language}."
    )

    astro_context = format_astro_payload(astro_payload)

    user_content = f"""Here is the astrological context:

{astro_context}

User's question: {_truncate_text(user_question, max_length=320)}

Please provide thoughtful cosmic guidance based on the astrological data above."""

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]


def format_astro_payload(payload: dict) -> str:
    def _safe_orb(value) -> str:
        if value is None:
            return "Unknown"
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "Unknown"
            try:
                return f"{float(stripped):.2f}"
            except ValueError:
                return stripped
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "Unknown"

    payload_data = _to_dict(payload)
    lines = []

    natal = _to_dict(payload_data.get("natal"))
    if natal:
        lines.append("=== NATAL CHART ===")
        natal_planets = _to_dict(natal.get("planets"))
        if natal_planets:
            lines.append("\nNatal Planets:")
            for planet, data in list(natal_planets.items())[:MAX_PLANETS_PER_SECTION]:
                lines.append(_format_planet_line(planet, data))

        houses = _to_dict(natal.get("houses"))
        if houses:
            lines.append(f"\nAscendant: {_truncate_text(houses.get('asc', 'Unknown'), max_length=40)}")
            lines.append(f"Midheaven: {_truncate_text(houses.get('mc', 'Unknown'), max_length=40)}")

    transits = _to_dict(payload_data.get("transits"))
    if transits:
        lines.append("\n=== CURRENT TRANSITS ===")
        transit_planets = _to_dict(transits.get("planets"))
        if transit_planets:
            lines.append("\nTransit Planets:")
            for planet, data in transits["planets"].items():
                lines.append(f"  - {planet}: {data.get('sign', 'Unknown')} ({data.get('deg_in_sign', 0):.1f})")
    
    if "aspects" in payload:
        aspects = payload["aspects"]
        if aspects:
            lines.append("\n=== KEY ASPECTS (Transit to Natal) ===")
            for asp in aspects[:10]:
                if not isinstance(asp, dict):
                    lines.append("  - Invalid aspect entry.")
                    continue

                transit_planet = asp.get("transit_planet", "Unknown")
                aspect_name = asp.get("aspect", "Unknown")
                natal_planet = asp.get("natal_planet", "Unknown")
                influence = asp.get("influence", "Unknown")
                orb = _safe_orb(asp.get("orb", "Unknown"))

                lines.append(
                    f"  - Transit {transit_planet} {aspect_name} Natal {natal_planet} "
                    f"(orb: {orb}) - {influence}"
                )
    
            for planet, data in list(transit_planets.items())[:MAX_PLANETS_PER_SECTION]:
                lines.append(_format_planet_line(planet, data))

    aspects = _to_list(payload_data.get("aspects"))
    if aspects:
        lines.append("\n=== KEY ASPECTS (Transit to Natal) ===")
        for asp in aspects[:MAX_ASPECTS]:
            asp_data = _to_dict(asp)
            lines.append(
                "  - Transit "
                f"{_truncate_text(asp_data.get('transit_planet', 'Unknown'), max_length=20)} "
                f"{_truncate_text(asp_data.get('aspect', 'aspect'), max_length=20)} Natal "
                f"{_truncate_text(asp_data.get('natal_planet', 'Unknown'), max_length=20)} "
                f"(orb: {_truncate_text(str(asp_data.get('orb', 'n/a')), max_length=10)}) - "
                f"{_truncate_text(asp_data.get('influence', 'No influence data'), max_length=MAX_TEXT_FIELD_LENGTH)}"
            )

    return "\n".join(lines) if lines else "No astrological data provided."
