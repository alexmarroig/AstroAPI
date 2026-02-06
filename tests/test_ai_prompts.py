import pytest
from pydantic import ValidationError

from ai.prompts import build_cosmic_chat_messages, format_astro_payload
from schemas.ai import CosmicChatRequest, MAX_USER_QUESTION_LENGTH


def test_format_astro_payload_handles_incomplete_payload():
    payload = {
        "natal": {"houses": {"asc": "Aries"}},
    }

    formatted = format_astro_payload(payload)

    assert "=== NATAL CHART ===" in formatted
    assert "Ascendant: Aries" in formatted


def test_format_astro_payload_handles_malformed_payload():
    payload = {
        "natal": "invalid",
        "transits": ["not a dict"],
        "aspects": ["invalid aspect", {"transit_planet": "Saturn"}],
    }

    formatted = format_astro_payload(payload)

    assert "KEY ASPECTS" in formatted
    assert "Transit Unknown aspect Natal Unknown" in formatted


def test_build_messages_truncates_large_payload_and_normalizes_defaults():
    huge_text = "muito longo " * 80
    aspects = [
        {
            "transit_planet": f"Planet-{i}",
            "aspect": "conjunction",
            "natal_planet": "Moon",
            "orb": i,
            "influence": huge_text,
        }
        for i in range(30)
    ]
    payload = {"aspects": aspects}

    messages = build_cosmic_chat_messages(
        user_question="Como devo navegar este período?",
        astro_payload=payload,
        tone=123,
        language="desconhecido",
    )

    system_message = messages[0]["content"]
    user_message = messages[1]["content"]

    assert "Respond in a calm, supportive, and reflective manner (fallback applied due to invalid tone input)." in system_message
    assert "Respond entirely in Portuguese (Brazil) (fallback applied due to invalid language input)." in system_message
    assert user_message.count("Transit Planet-") == 10
    assert "..." in user_message


def test_cosmic_chat_request_rejects_too_large_payload():
    with pytest.raises(ValidationError):
        CosmicChatRequest(
            user_question="oi",
            astro_payload={"aspects": [{"influence": "x" * 3000}]},
            language="pt-BR",
        )


def test_cosmic_chat_request_rejects_payload_with_too_many_items():
    with pytest.raises(ValidationError):
        CosmicChatRequest(
            user_question="oi",
            astro_payload={"aspects": [{"influence": "ok"}] * 250},
            language="pt-BR",
        )


def test_cosmic_chat_request_rejects_too_long_question():
    with pytest.raises(ValidationError):
        CosmicChatRequest(
            user_question="a" * (MAX_USER_QUESTION_LENGTH + 1),
            astro_payload={"natal": {}},
            language="pt-BR",
        )
