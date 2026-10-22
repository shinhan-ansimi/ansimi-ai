"""서울시 안심귀갓길 경로 (OA-21695) 수집.

서울시가 공식 지정한 362개 안심귀갓길의 선형(링크) 데이터. 포인트가 아니라 LineString이라
다른 카테고리들과 스키마가 다름 — grid.py에서 "이 격자가 공식 안심귀갓길 구간을 지나는가"
(on_safe_route) feature를 만드는 데 쓴다.

실제 배포 형식은 Open API 샘플 URL이 안 보여서(JS 렌더링) 확인 못 했고, SHP/XLSX 다운로드가
확실히 제공되는 걸 확인했음. 그래서 기본 경로는 "파일 다운로드 후 geopandas로 읽기"로 짜고,
Open API로도 되는 걸 확인하면 fetch_seoul_openapi 경로를 추가하면 된다.
"""
from __future__ import annotations

import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from ..config import settings

logger = logging.getLogger(__name__)

N_MOCK_ROUTES = 362  # 실제 공개된 안심귀갓길 개수(2023.04 기준)


def load_from_file(shp_path: str) -> gpd.GeoDataFrame:
    """OA-21695 에서 받은 '안심귀갓길 경로 데이터_SHP.zip' 압축을 풀고 그 안의 .shp 경로를 넘기면 됨."""
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None:
        raise ValueError("SHP 파일에 좌표계(CRS) 정보가 없습니다 — 데이터 제공처에 확인 필요")
    return gdf.to_crs(settings.wgs84_crs)


def generate_mock(rng: np.random.Generator, n_routes: int = N_MOCK_ROUTES) -> gpd.GeoDataFrame:
    """실제 경로 형태 대신, bbox 안에서 짧은 랜덤워크 폴리라인 n_routes개를 생성."""
    min_lon, max_lon = settings.bbox_min_lon, settings.bbox_max_lon
    min_lat, max_lat = settings.bbox_min_lat, settings.bbox_max_lat

    lines = []
    for i in range(n_routes):
        start_lon = rng.uniform(min_lon, max_lon)
        start_lat = rng.uniform(min_lat, max_lat)
        n_points = rng.integers(4, 10)
        step = 0.0015  # 대략 100~150m 간격
        lon = start_lon + np.cumsum(rng.normal(0, step, size=n_points))
        lat = start_lat + np.cumsum(rng.normal(0, step, size=n_points))
        lon = np.clip(lon, min_lon, max_lon)
        lat = np.clip(lat, min_lat, max_lat)
        lines.append(LineString(zip(lon, lat)))

    return gpd.GeoDataFrame(
        {"route_id": [f"SAFE_ROUTE_{i:04d}" for i in range(n_routes)], "source": "안심귀갓길 경로(mock)"},
        geometry=lines,
        crs=settings.wgs84_crs,
    )


def collect(rng: np.random.Generator) -> gpd.GeoDataFrame:
    if not settings.use_mock:
        shp_path = os.environ.get("SEOUL_SAFE_ROUTE_SHP")
        if shp_path and os.path.exists(shp_path):
            return load_from_file(shp_path)
        logger.warning("[safe_route] SEOUL_SAFE_ROUTE_SHP 미설정/파일 없음 → mock 데이터로 대체")

    return generate_mock(rng)
