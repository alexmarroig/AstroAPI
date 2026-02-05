from ai.prompts import format_astro_payload


def test_format_astro_payload_aspects_handles_missing_fields():
    payload = {
        "aspects": [
            {
                "transit_planet": "Mars",
                "aspect": "Square",
                "natal_planet": "Saturn",
            },
            {
                "transit_planet": "Venus",
                "aspect": "Trine",
                "natal_planet": "Moon",
                "orb": " 1.5 ",
                "influence": "Soothing emotional tone",
            },
        ]
    }

    formatted = format_astro_payload(payload)

    assert isinstance(formatted, str)
    assert "Transit Mars Square Natal Saturn (orb: Unknown) - Unknown" in formatted
    assert "Transit Venus Trine Natal Moon (orb: 1.50) - Soothing emotional tone" in formatted


def test_format_astro_payload_aspects_handles_invalid_entries_without_crashing():
    payload = {
        "aspects": [
            None,
            "not-a-dict",
            {
                "transit_planet": "Sun",
                "aspect": "Opposition",
                "natal_planet": "Neptune",
                "orb": "n/a",
                "influence": "Confusing but creative",
            },
        ]
    }

    formatted = format_astro_payload(payload)

    assert isinstance(formatted, str)
    assert formatted.count("Invalid aspect entry.") == 2
    assert "Transit Sun Opposition Natal Neptune (orb: n/a) - Confusing but creative" in formatted
