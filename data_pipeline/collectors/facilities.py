"""
포인트형 안전시설 데이터 수집 공통 로직.

CCTV / 보안등 / 안전비상벨 / 경찰관서 / 24시 편의점은 전부
"위경도 포인트 + 자치구" 스키마로 귀결되므로 공통 함수 하나로 처리하고,
cctv.py / security_light.py / emergency_bell.py / police.py / convenience_store.py
는 이 함수를 각자의 서비스명으로 호출하는 thin wrapper로 둔다.

실제 서비스명(service_name)은 데이터셋마다, 심지어 자치구마다 다른 경우가 많다.
서울 열린데이터광장에 가입 후 "Open API 서비스 신청" 메뉴에서 본인 계정에
할당된 정확한 서비스명을 확인해서 SERVICE_NAME_MAP 에 채워 넣으면 그대로 동작한다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import get_seoul_key, settings
from .base import fetch_seoul_openapi, random_points_in_bbox

logger = logging.getLogger(__name__)

# mock 모드에서 "이 카테고리는 대략 이 정도 개수가 서울 전역에 있다"를 흉내내기 위한 규모감.
# (실제 수치가 아니라, 기사/데이터셋 소개 페이지에 공개된 대략적 규모를 참고한 자릿수 수준의 추정치)
MOCK_SCALE = {
    "cctv": 7000,
    "security_light": 4000,
    "emergency_bell": 2500,
    "police": 260,
    "convenience_store": 3000,
    "route_cctv": 1487,  # 안심귀갓길 안전시설물(OA-21696) 실데이터 기준 실제 건수
    "route_emergency_bell": 1001,
    "route_signage": 376,
    "route_security_light": 5618,
    "safe_delivery_box": 400,
    "safe_route_guardian_house": 300,
}


def collect_point_facility(
    category: str,
    source: str,
    service_name: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """카테고리 하나에 대한 포인트형 시설 데이터 수집.

    1) USE_MOCK=0 이고 키가 있으면 실제 Open API 호출을 시도한다.
    2) 실패하거나 mock 모드면 샘플 데이터로 대체한다 (로그로 명확히 표시).
    """
    if not settings.use_mock:
        try:
            api_key = get_seoul_key(category)
            raw_rows = fetch_seoul_openapi(service_name, api_key)
            df = pd.json_normalize(raw_rows)
            df = _normalize_real_columns(df, category, source)
            logger.info("[%s] 실제 API에서 %d건 수집", category, len(df))
            return df
        except Exception as exc:  # noqa: BLE001 - 수집 실패는 흔하므로 mock으로 폴백
            logger.warning("[%s] 실제 API 호출 실패(%s) → mock 데이터로 대체", category, exc)

    n = MOCK_SCALE.get(category, 1000)
    df = random_points_in_bbox(n=n, category=category, source=f"{source}(mock)", rng=rng)
    return df


def _normalize_real_columns(df: pd.DataFrame, category: str, source: str) -> pd.DataFrame:
    """서울 열린데이터광장 원본 컬럼명은 데이터셋마다 제각각이라
    위도/경도/자치구/명칭으로 추정되는 컬럼을 느슨하게 매칭해 표준 스키마로 맞춘다.
    실제 데이터를 한 번 받아보고 정확한 컬럼명으로 이 매핑을 확정해야 한다(README 참고).
    """
    lat_col = _find_col(df, ["위도", "LAT", "lat", "Y좌표", "Y_CRTR"])
    lon_col = _find_col(df, ["경도", "LOT", "LON", "lon", "X좌표", "X_CRTR"])
    name_col = _find_col(df, ["명칭", "설치장소", "ADDR", "안전시설명", "NAME"])
    gu_col = _find_col(df, ["자치구", "구", "SIGUNGU", "GUNAME"])

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df[lat_col], errors="coerce") if lat_col else np.nan
    out["lon"] = pd.to_numeric(df[lon_col], errors="coerce") if lon_col else np.nan
    out["name"] = df[name_col] if name_col else f"{category}"
    out["gu"] = df[gu_col] if gu_col else None
    out["category"] = category
    out["source"] = source
    return out.dropna(subset=["lat", "lon"])


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None
