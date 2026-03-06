from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from schemas.checkin import CheckinEntry, CheckinHistoryResponse, CheckinSubmitRequest, CheckinSubmitResponse
from services.checkin_engine import build_cosmic_context, detect_checkin_pattern, get_history, save_checkin

from .common import get_auth

router = APIRouter()


@router.post("/v1/checkin/submit", response_model=CheckinSubmitResponse)
async def submit_checkin(body: CheckinSubmitRequest, auth=Depends(get_auth)):
    user_id = auth["user_id"]
    try:
        entry_dict = await save_checkin(user_id=user_id, state=body.state)
        history = await get_history(user_id=user_id, limit=20)
        pattern = detect_checkin_pattern(history)
        entry = CheckinEntry(**entry_dict)
        return CheckinSubmitResponse(
            entry=entry,
            cosmic_context=build_cosmic_context(entry_dict),
            pattern=pattern,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Falha ao registrar check-in: {exc}") from exc


@router.get("/v1/checkin/history", response_model=CheckinHistoryResponse)
async def checkin_history(limit: int = Query(12, ge=1, le=60), auth=Depends(get_auth)):
    user_id = auth["user_id"]
    try:
        history = await get_history(user_id=user_id, limit=limit)
        entries = [CheckinEntry(**item) for item in history]
        pattern = detect_checkin_pattern(history)
        return CheckinHistoryResponse(entries=entries, pattern=pattern)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Falha ao carregar historico de check-in: {exc}") from exc
