"""안전비상벨(안심벨) 설치 위치 수집.

행정안전부_안전비상벨위치정보 조회서비스(data.go.kr 15155046)를 쓴다. REST, 서울만
주소 필터로 서버사이드에서 걸러 받는다. 응답 필드명은 WGS84_LAT/LOT인데 메타데이터는
EPSG:5174(TM)라고 돼있어 모순이라, 값 범위로 실제 좌표계를 검증한다.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from ..config import settings
from .base import fetch_data_go_kr, random_points_in_bbox
from .facilities import MOCK_SCALE

logger = logging.getLogger(__name__)

STANDARD_ENDPOINT = "https://apis.data.go.kr/1741000/emergency_call_box_info/info"
STANDARD_SOURCE = "행정안전부 안전비상벨위치정보 조회서비스"


def _load_from_standard_api(api_key: str) -> pd.DataFrame:
    raw_rows = fetch_data_go_kr(
        STANDARD_ENDPOINT,
        extra_params={"returnType": "json", "cond[LCTN_ROAD_NM_ADDR::LIKE]": "서울특별시"},
        api_key=api_key,
        num_of_rows=100,  # 이 API는 한 페이지 최대 100건(다른 data.go.kr API들의 1000과 다름)
        max_rows=20000,
    )
    df = pd.json_normalize(raw_rows)
    if df.empty:
        return pd.DataFrame(columns=["lat", "lon", "name", "gu", "category", "source"])

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df["WGS84_LAT"], errors="coerce")
    out["lon"] = pd.to_numeric(df["WGS84_LOT"], errors="coerce")

    if out["lat"].notna().any() and not out["lat"].between(33, 43).all():
        raise RuntimeError("WGS84_LAT/LOT이 위경도 범위를 벗어남 — EPSG:5174(TM)로 보임, 변환 필요")

    addr = df.get("LCTN_ROAD_NM_ADDR")
    out["name"] = addr.fillna(df.get("LCTN_LOTNO_ADDR")) if addr is not None else None
    out["gu"] = addr.astype(str).str.extract(r"([가-힣]+구)") if addr is not None else None
    out["category"] = "emergency_bell"
    out["source"] = STANDARD_SOURCE
    return out.dropna(subset=["lat", "lon"])


def collect(rng: np.random.Generator) -> pd.DataFrame:
    api_key = os.environ.get("DATA_GO_KR_EMERGENCY_BELL_KEY") or settings.data_go_kr_key
    if not settings.use_mock and api_key:
        try:
            df = _load_from_standard_api(api_key)
            logger.info("[emergency_bell] 안전비상벨 표준 API에서 %d건 수집", len(df))
            return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("[emergency_bell] 표준 API 호출 실패(%s) → mock으로 대체", exc)

    return random_points_in_bbox(n=MOCK_SCALE["emergency_bell"], category="emergency_bell", source="안전비상벨(mock)", rng=rng)
