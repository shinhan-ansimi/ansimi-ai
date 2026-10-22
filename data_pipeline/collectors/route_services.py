"""서울시 안심귀갓길 서비스 (OA-21697) 수집.

안심귀갓길 인근의 안심택배함 / 안심귀가길 지킴이집 위치. OA-21696과 마찬가지로
시설 종류 컬럼 하나에 두 종류가 섞여 내려올 가능성이 높아 동일한 방식으로 분리한다.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import get_seoul_key, settings
from .base import fetch_seoul_openapi, random_points_in_bbox
from .facilities import MOCK_SCALE, _normalize_real_columns

logger = logging.getLogger(__name__)

SOURCE = "서울시 안심귀갓길 서비스 (OA-21697)"
SERVICE_NAME = "TbSafeReturnRoadService"  # TODO: 실제 발급받은 서비스명으로 교체

FACILITY_TYPE_COLUMN_CANDIDATES = ["시설구분", "시설종류", "FCLTY_TY", "FCLTY_SE_NM"]
FACILITY_TYPE_KEYWORDS = {
    "safe_delivery_box": ["택배"],
    "safe_route_guardian_house": ["지킴이"],
}


def _classify(df: pd.DataFrame) -> pd.DataFrame:
    type_col = next((c for c in FACILITY_TYPE_COLUMN_CANDIDATES if c in df.columns), None)
    if type_col is None:
        logger.warning("[route_services] 시설구분 컬럼을 못 찾아서 전부 safe_route_guardian_house로 둠 — 컬럼명 확인 필요")
        df["category"] = "safe_route_guardian_house"
        return df

    def _match(value: str) -> str:
        for cat, keywords in FACILITY_TYPE_KEYWORDS.items():
            if any(k in str(value) for k in keywords):
                return cat
        return "safe_route_guardian_house"

    df["category"] = df[type_col].map(_match)
    return df


def collect(rng: np.random.Generator) -> pd.DataFrame:
    if not settings.use_mock:
        try:
            api_key = get_seoul_key("route_service")
            raw_rows = fetch_seoul_openapi(SERVICE_NAME, api_key)
            df = pd.json_normalize(raw_rows)
            df = _classify(df)
            frames = []
            for cat in ["safe_delivery_box", "safe_route_guardian_house"]:
                sub = df[df["category"] == cat]
                frames.append(_normalize_real_columns(sub, cat, SOURCE))
            out = pd.concat(frames, ignore_index=True)
            logger.info("[route_services] 실제 API에서 %d건 수집", len(out))
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("[route_services] 실제 API 호출 실패(%s) → mock 데이터로 대체", exc)

    frames = [
        random_points_in_bbox(n=MOCK_SCALE[cat], category=cat, source=f"{SOURCE}(mock)", rng=rng)
        for cat in ["safe_delivery_box", "safe_route_guardian_house"]
    ]
    return pd.concat(frames, ignore_index=True)
