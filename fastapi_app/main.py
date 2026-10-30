"""2.3 스코어링 API — risk_grid.csv(safety_score 포함)를 좌표 기준으로 조회한다.

실행:
    cd ansimi-ai
    uvicorn fastapi_app.main:app --reload
    curl "http://127.0.0.1:8000/score?lat=37.5665&lon=126.9780"
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from .score import GridIndex

_index: GridIndex | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _index
    _index = GridIndex()
    yield


app = FastAPI(title="안심이 스코어링 API", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "cells": len(_index.df) if _index else 0}


@app.get("/score")
def get_score(
    lat: float = Query(..., ge=-90, le=90, description="위도"),
    lon: float = Query(..., ge=-180, le=180, description="경도"),
) -> dict:
    if _index is None:
        raise HTTPException(status_code=503, detail="격자 데이터가 아직 로드되지 않았습니다.")
    if not _index.in_coverage(lat, lon):
        raise HTTPException(status_code=400, detail="서울 격자 범위 밖 좌표입니다.")

    cell = _index.nearest(lat, lon)
    return {
        "grid_id": int(cell["grid_id"]),
        "safety_score": float(cell["safety_score"]),
        "on_safe_route": bool(cell["on_safe_route"]),
        "center_lat": float(cell["center_lat"]),
        "center_lon": float(cell["center_lon"]),
    }
