from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.interpretation_repository import InterpretationRepository


def _safe_content(content: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "summary": str(content.get("summary", "")).strip(),
        "interpretation": str(content.get("interpretation", "")).strip(),
        "nuance": str(content.get("nuance", "")).strip(),
        "growth": str(content.get("growth", "")).strip(),
        "questions": [str(item).strip() for item in (content.get("questions") or []) if str(item).strip()],
    }


def _merge_modules(modules: List[Dict[str, Any]]) -> Dict[str, Any]:
    summaries: List[str] = []
    interpretations: List[str] = []
    nuances: List[str] = []
    growth_points: List[str] = []
    questions: List[str] = []

    for module in modules:
        content = _safe_content(module.get("content", {}))
        if content["summary"]:
            summaries.append(content["summary"])
        if content["interpretation"]:
            interpretations.append(content["interpretation"])
        if content["nuance"]:
            nuances.append(content["nuance"])
        if content["growth"]:
            growth_points.append(content["growth"])
        questions.extend(content["questions"])

    return {
        "summary": " ".join(summaries[:6]).strip(),
        "interpretation": "\n\n".join(interpretations[:8]).strip(),
        "nuance": "\n".join(nuances[:6]).strip(),
        "growth": "\n".join(growth_points[:6]).strip(),
        "questions": questions[:10],
    }


async def _ai_summarize_if_enabled(
    *,
    request: Any,
    language: str,
    use_ai_summary: bool,
    merged: Dict[str, Any],
) -> Optional[str]:
    if not use_ai_summary:
        return None
    client = getattr(request.app.state, "openai_client", None)
    if client is None:
        return None

    prompt = (
        "Create a concise, reflective astrology narrative. "
        "Avoid deterministic predictions. Keep practical and grounded.\n\n"
        f"Language: {language}\n"
        f"Summary: {merged.get('summary', '')}\n"
        f"Interpretation: {merged.get('interpretation', '')}\n"
        f"Nuance: {merged.get('nuance', '')}\n"
        f"Growth: {merged.get('growth', '')}\n"
        f"Questions: {', '.join(merged.get('questions', []))}\n"
    )
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an astrology interpretation editor."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=350,
    )
    return response.choices[0].message.content if response.choices else None


async def generate_interpretation(
    *,
    request: Any,
    chart: Dict[str, Any],
    use_ai_summary: bool,
    language: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    repository = InterpretationRepository()
    modules = await repository.find_modules_for_chart(chart)
    merged = _merge_modules(modules)
    ai_narrative = await _ai_summarize_if_enabled(
        request=request,
        language=language,
        use_ai_summary=use_ai_summary,
        merged=merged,
    )

    return {
        "modules_count": len(modules),
        "summary": merged["summary"],
        "interpretation": merged["interpretation"],
        "nuance": merged["nuance"],
        "growth": merged["growth"],
        "questions": merged["questions"],
        "ai_narrative": ai_narrative,
        "method": "modules+rules" if not ai_narrative else "modules+rules+ai",
        "disclaimer": "Interpretacao reflexiva; nao deterministica.",
    }, modules
