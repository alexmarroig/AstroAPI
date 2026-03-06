from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List


SECTION_ORDER = [
    "Introduction",
    "Identity",
    "Emotions",
    "Relationships",
    "Challenges",
    "Growth",
    "Closing reflection",
]


def _normalize_key(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _to_reflective(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    replacements = [
        ("you will", "you may"),
        ("you must", "you might consider"),
        ("you are destined", "you may feel drawn"),
        ("always", "often"),
        ("never", "rarely"),
        ("guaranteed", "more likely"),
        ("certainly", "potentially"),
    ]
    lower = cleaned.lower()
    for src, dst in replacements:
        lower = lower.replace(src, dst)
    if not lower:
        return ""
    return lower[0].upper() + lower[1:]


def _unique_texts(chunks: List[str]) -> List[str]:
    seen = set()
    output = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        key = _normalize_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        output.append(_to_reflective(chunk))
    return output


def _classify_text(theme: str, text: str, field: str) -> str:
    if field == "shadow":
        return "Challenges"
    if field == "integration":
        return "Growth"

    corpus = f"{theme} {text}".lower()
    if any(token in corpus for token in ("identity", "self", "purpose", "ego", "sun")):
        return "Identity"
    if any(token in corpus for token in ("emotion", "feeling", "mood", "attachment", "moon")):
        return "Emotions"
    if any(token in corpus for token in ("relationship", "partner", "love", "bond", "venus", "synastry")):
        return "Relationships"
    if any(token in corpus for token in ("growth", "integration", "maturity", "development", "saturn", "jupiter")):
        return "Growth"
    return "Identity"


def _chapter_paragraph(lines: List[str], default_text: str, limit: int = 4) -> str:
    selected = _unique_texts(lines)[:limit]
    if not selected:
        return default_text
    paragraph = " ".join(selected)
    if not paragraph.endswith("."):
        paragraph += "."
    return paragraph


def compose_narrative_from_modules(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not modules:
        empty_sections = {name: "No modules were provided for this section." for name in SECTION_ORDER}
        return {"sections": empty_sections, "full_text": "\n\n".join(f"{k}\n{v}" for k, v in empty_sections.items())}

    grouped: Dict[str, List[str]] = defaultdict(list)
    intro_lines: List[str] = []
    closing_questions: List[str] = []

    for module in modules:
        theme = str(module.get("theme", "")).strip()
        summary = str(module.get("summary", "")).strip()
        interpretation = str(module.get("interpretation", "")).strip()
        shadow = str(module.get("shadow", "")).strip()
        integration = str(module.get("integration", "")).strip()
        questions = module.get("questions") or []

        if summary:
            intro_lines.append(summary)

        for field, value in (
            ("interpretation", interpretation),
            ("shadow", shadow),
            ("integration", integration),
        ):
            if value:
                section = _classify_text(theme, value, field)
                grouped[section].append(value)

        for q in questions:
            q_text = str(q).strip()
            if q_text:
                closing_questions.append(q_text)

    sections = {
        "Introduction": _chapter_paragraph(
            intro_lines,
            "This interpretation explores symbolic patterns as evolving tendencies rather than fixed outcomes.",
            limit=5,
        ),
        "Identity": _chapter_paragraph(
            grouped.get("Identity", []),
            "Identity themes suggest an ongoing dialogue between self-definition and adaptation.",
            limit=5,
        ),
        "Emotions": _chapter_paragraph(
            grouped.get("Emotions", []),
            "Emotional themes invite awareness of regulation patterns, vulnerability, and internal safety.",
            limit=5,
        ),
        "Relationships": _chapter_paragraph(
            grouped.get("Relationships", []),
            "Relationship themes often mirror inner dynamics and offer opportunities for mutual growth.",
            limit=5,
        ),
        "Challenges": _chapter_paragraph(
            grouped.get("Challenges", []),
            "Challenges may signal protective strategies that once helped and now request refinement.",
            limit=5,
        ),
        "Growth": _chapter_paragraph(
            grouped.get("Growth", []),
            "Growth themes emphasize integration through consistent, values-aligned choices.",
            limit=5,
        ),
        "Closing reflection": _chapter_paragraph(
            closing_questions,
            "As a closing reflection, notice which symbolic theme feels most alive and what practical step you can take next.",
            limit=4,
        ),
    }

    full_text = "\n\n".join(f"{name}\n{sections[name]}" for name in SECTION_ORDER)
    return {"sections": sections, "full_text": full_text}
