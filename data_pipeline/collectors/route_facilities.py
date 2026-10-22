"""서울시 안심귀갓길 안전시설물 (OA-21696) 수집.

Seoul API는 서비스명이 확정 안 돼 죽어있어서, 실제로 받은 SHP 파일(`ROUTE_FACILITY_SHP`)을
쓴다. 시설코드 정의(안심귀갓길_안전시설물(코드유형).xlsx)로 확인한 매핑:
301 안심벨, 302 CCTV, 303 안내표지판, 305 보안등 — 이 4종만 쓰고 304(노면표기)/
306(서비스안내판)/307(112안내)/308(기타)는 안전도 신호로서 가치가 낮아 제외했다.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from ..config import settings
from .base import random_points_in_bbox
from .facilities import MOCK_SCALE

logger = logging.getLogger(__name__)

SOURCE = "서울시 안심귀갓길 안전시설물 (OA-21696)"

CODE_TO_CATEGORY = {
    "301": "route_emergency_bell",
    "302": "route_cctv",
    "303": "route_signage",
    "305": "route_security_light",
}
CATEGORIES = list(CODE_TO_CATEGORY.values())


def load_from_file(path: str) -> pd.DataFrame:
    import geopandas as gpd

    gdf = gpd.read_file(path, encoding="cp949")
    gdf["category"] = gdf["시설코드"].astype(str).map(CODE_TO_CATEGORY)
    gdf = gdf[gdf["category"].notna()]

    out = pd.DataFrame()
    out["lat"] = gdf.geometry.y
    out["lon"] = gdf.geometry.x
    out["name"] = gdf.get("세부위치")
    out["gu"] = gdf["시군구명"].str.replace("서울특별시 ", "", regex=False)
    out["category"] = gdf["category"]
    out["source"] = SOURCE
    return out.dropna(subset=["lat", "lon"])


def collect(rng: np.random.Generator) -> pd.DataFrame:
    shp_path = os.environ.get("ROUTE_FACILITY_SHP")
    if not settings.use_mock and shp_path and os.path.exists(shp_path):
        df = load_from_file(shp_path)
        logger.info("[route_facilities] SHP 파일에서 %d건 수집", len(df))
        return df

    frames = [
        random_points_in_bbox(n=MOCK_SCALE[cat], category=cat, source=f"{SOURCE}(mock)", rng=rng)
        for cat in CATEGORIES
    ]
    return pd.concat(frames, ignore_index=True)
