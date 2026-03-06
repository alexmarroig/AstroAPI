from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request

from core.redis_cache import redis_cache
from schemas.modular_engine import (
    ChartInput,
    ChartResponse,
    InterpretationModuleOut,
    InterpretationRequest,
    InterpretationRefineRequest,
    InterpretationRefineResponse,
    InterpretationResponse,
    ModuleCompositionRequest,
    ModuleCompositionResponse,
    NarrativeRequest,
    NarrativeResponse,
    NarrativeCompositionRequest,
    NarrativeCompositionResponse,
)
from services.modular_chart_engine import build_positions_hash, compute_birth_chart
from services.module_composition_engine import compose_module_report
from services.modular_interpretation_engine import generate_interpretation
from services.narrative_composition_engine import compose_narrative_from_modules
from services.narrative_engine import generate_structured_narrative

from .common import get_auth

router = APIRouter()
CHART_CACHE_TTL_SECONDS = 30 * 24 * 3600
INTERPRETATION_CACHE_TTL_SECONDS = 7 * 24 * 3600
REFINED_CACHE_TTL_SECONDS = 7 * 24 * 3600


def _normalize_content(raw: dict) -> dict:
    return {
        "summary": str(raw.get("summary", "")).strip(),
        "interpretation": str(raw.get("interpretation", "")).strip(),
        "nuance": str(raw.get("nuance", "")).strip(),
        "growth": str(raw.get("growth", "")).strip(),
        "questions": [str(item).strip() for item in (raw.get("questions") or []) if str(item).strip()],
    }


def _build_interp_cache_key(chart_hash: str, language: str, version: str) -> str:
    return f"interp:{chart_hash}:lang:{language.lower()}:v:{version}"


def _build_refined_cache_key(chart_hash: str, language: str, style: str, version: str) -> str:
    return f"refined:{chart_hash}:lang:{language.lower()}:style:{style}:v:{version}"


async def _get_chart_by_hash(chart_hash: str) -> dict | None:
    return await redis_cache.get_json(f"chart:{chart_hash}")


@router.post("/chart", response_model=ChartResponse)
async def chart_endpoint(body: ChartInput, auth=Depends(get_auth)):
    try:
        payload = compute_birth_chart(body.model_dump())
        chart = payload["chart"]
        chart_hash = build_positions_hash(chart)
        await redis_cache.set_json(f"chart:{chart_hash}", chart, ttl_seconds=CHART_CACHE_TTL_SECONDS)
        return ChartResponse(chart_hash=chart_hash, chart=chart)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Chart calculation failed: {exc}") from exc


@router.post("/interpretation", response_model=InterpretationResponse)
async def interpretation_endpoint(body: InterpretationRequest, request: Request, auth=Depends(get_auth)):
    try:
        chart_hash: str | None = body.chart_hash
        chart: dict | None = None

        if chart_hash:
            chart = await _get_chart_by_hash(chart_hash)
            if chart is None:
                if body.chart_input is None and body.chart is None:
                    raise HTTPException(
                        status_code=404,
                        detail="chart_hash nao encontrado em cache. Envie /chart antes ou inclua chart_input/chart.",
                    )

        if chart is None and body.chart_input is not None:
            chart_payload = compute_birth_chart(body.chart_input.model_dump())
            chart = chart_payload["chart"]

        if chart is None:
            raw_chart = body.chart or {}
            if "chart" in raw_chart and isinstance(raw_chart.get("chart"), dict):
                chart = raw_chart.get("chart", {})
            else:
                chart = raw_chart

        chart_hash = build_positions_hash(chart)
        await redis_cache.set_json(f"chart:{chart_hash}", chart, ttl_seconds=CHART_CACHE_TTL_SECONDS)
        cache_key = _build_interp_cache_key(chart_hash, body.language, body.version)

        cached = await redis_cache.get_json(cache_key)
        if cached:
            return InterpretationResponse(**cached)

        final, raw_modules = await generate_interpretation(
            request=request,
            chart=chart,
            use_ai_summary=False,
            language=body.language,
        )
        modules = [
            InterpretationModuleOut(
                id=str(item.get("id")),
                type=str(item.get("type", "")),
                planet=item.get("planet"),
                sign=item.get("sign"),
                house=item.get("house"),
                aspect=item.get("aspect"),
                content=_normalize_content(item.get("content", {})),
            )
            for item in raw_modules
        ]
        response = InterpretationResponse(
            chart_hash=chart_hash,
            chart=chart,
            modules=modules,
            final_interpretation=final,
            method="deterministic",
            cache_key=cache_key,
        )
        await redis_cache.set_json(
            cache_key,
            response.model_dump(),
            ttl_seconds=INTERPRETATION_CACHE_TTL_SECONDS,
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Interpretation generation failed: {exc}") from exc


@router.post("/interpretation/refine", response_model=InterpretationRefineResponse)
async def interpretation_refine_endpoint(body: InterpretationRefineRequest, request: Request, auth=Depends(get_auth)):
    try:
        deterministic_key = _build_interp_cache_key(body.chart_hash, body.language, body.version)
        refined_key = _build_refined_cache_key(body.chart_hash, body.language, body.style, body.version)

        if not body.force_refresh:
            cached_refined = await redis_cache.get_json(refined_key)
            if cached_refined:
                return InterpretationRefineResponse(**cached_refined)

        deterministic_payload = await redis_cache.get_json(deterministic_key)
        if deterministic_payload is None:
            chart = await _get_chart_by_hash(body.chart_hash)
            if chart is None:
                raise HTTPException(
                    status_code=404,
                    detail="Interpretacao base nao encontrada para chart_hash informado.",
                )
            final, raw_modules = await generate_interpretation(
                request=request,
                chart=chart,
                use_ai_summary=False,
                language=body.language,
            )
            modules = [
                InterpretationModuleOut(
                    id=str(item.get("id")),
                    type=str(item.get("type", "")),
                    planet=item.get("planet"),
                    sign=item.get("sign"),
                    house=item.get("house"),
                    aspect=item.get("aspect"),
                    content=_normalize_content(item.get("content", {})),
                )
                for item in raw_modules
            ]
            deterministic_response = InterpretationResponse(
                chart_hash=body.chart_hash,
                chart=chart,
                modules=modules,
                final_interpretation=final,
                method="deterministic",
                cache_key=deterministic_key,
            )
            deterministic_payload = deterministic_response.model_dump()
            await redis_cache.set_json(
                deterministic_key,
                deterministic_payload,
                ttl_seconds=INTERPRETATION_CACHE_TTL_SECONDS,
            )

        final_interpretation = deterministic_payload.get("final_interpretation", {})
        deterministic_text = str(final_interpretation.get("interpretation") or final_interpretation.get("summary") or "").strip()
        if not deterministic_text:
            deterministic_text = "Nenhum texto disponivel para refinamento."

        client = getattr(request.app.state, "openai_client", None)
        if client is None:
            fallback = InterpretationRefineResponse(
                chart_hash=body.chart_hash,
                language=body.language,
                style=body.style,
                version=body.version,
                refined_text=deterministic_text,
                source="fallback",
                cache_key=refined_key,
            )
            await redis_cache.set_json(refined_key, fallback.model_dump(), ttl_seconds=REFINED_CACHE_TTL_SECONDS)
            return fallback

        max_tokens = int(os.getenv("OPENAI_REFINE_MAX_TOKENS", "500"))
        timeout_s = float(os.getenv("OPENAI_REFINE_TIMEOUT_SECONDS", "20"))
        prompt = (
            "Rewrite the text for clarity and flow but do not add or alter any astrological facts.\n"
            "Keep a reflective, non-deterministic tone.\n"
            f"Language: {body.language}\n"
            f"Style: {body.style}\n\n"
            f"Text:\n{deterministic_text}"
        )

        try:
            completion = await client.chat.completions.create(
                model=os.getenv("OPENAI_REFINE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
                messages=[
                    {"role": "system", "content": "You are a text editor. Never change astrological facts."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
                timeout=timeout_s,
            )
            refined_text = str(completion.choices[0].message.content or "").strip() if completion.choices else ""
            if not refined_text:
                raise RuntimeError("Resposta vazia no refinamento")
            response = InterpretationRefineResponse(
                chart_hash=body.chart_hash,
                language=body.language,
                style=body.style,
                version=body.version,
                refined_text=refined_text,
                source="llm",
                cache_key=refined_key,
            )
        except Exception:
            response = InterpretationRefineResponse(
                chart_hash=body.chart_hash,
                language=body.language,
                style=body.style,
                version=body.version,
                refined_text=deterministic_text,
                source="fallback",
                cache_key=refined_key,
            )

        await redis_cache.set_json(refined_key, response.model_dump(), ttl_seconds=REFINED_CACHE_TTL_SECONDS)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Interpretation refinement failed: {exc}") from exc


@router.post("/interpretation/compose", response_model=ModuleCompositionResponse)
async def interpretation_compose_endpoint(body: ModuleCompositionRequest, auth=Depends(get_auth)):
    try:
        report = await compose_module_report(body.birth_chart)
        return ModuleCompositionResponse(**report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Module composition failed: {exc}") from exc


@router.post("/interpretation/narrative", response_model=NarrativeResponse)
async def interpretation_narrative_endpoint(body: NarrativeRequest, auth=Depends(get_auth)):
    try:
        payload = await generate_structured_narrative(body.birth_chart)
        return NarrativeResponse(**payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Narrative generation failed: {exc}") from exc


@router.post("/interpretation/narrative/compose", response_model=NarrativeCompositionResponse)
async def interpretation_narrative_compose_endpoint(body: NarrativeCompositionRequest, auth=Depends(get_auth)):
    try:
        payload = compose_narrative_from_modules([item.model_dump() for item in body.modules])
        return NarrativeCompositionResponse(**payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Narrative composition failed: {exc}") from exc
