from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.access import owner_dependency
from core.run_lifecycle import RunConflict, get_run, list_runs, request_cancel
from core.runtime_status import component_runtime_status


router = APIRouter(prefix="/api/v1/runtime", tags=["Runtime"])


@router.get("/components")
def components():
    return component_runtime_status()


@router.get("/runs")
def runs(limit: int = Query(100, ge=1, le=500), status: str = ""):
    try:
        return list_runs(limit, status)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/runs/{run_id}")
def run(run_id: str):
    try:
        return get_run(run_id)
    except (KeyError, ValueError) as error:
        raise HTTPException(404, "Run non trovato.") from error


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(owner_dependency("runtime"))])
def cancel_run(run_id: str):
    try:
        return request_cancel(run_id)
    except (RunConflict, ValueError) as error:
        raise HTTPException(409, str(error)) from error
