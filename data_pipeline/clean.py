"""2.1 정제 — 수집된 원본 데이터를 공통 스키마로 표준화.

- 포인트형 안전시설(cctv/security_light/emergency_bell/police/convenience_store/안심귀갓길 연계 등):
  공통 스키마 [source, category, name, lat, lon, gu] 로 합치고
    1) 서울 bbox 밖 좌표 제거 (좌표 오입력/좌표계 혼동 방지)
    2) 결측치(lat/lon 없는 행) 제거
    3) 중복 포인트 제거(거의 동일 위치 + 동일 카테고리)
  를 수행한다.

- 자치구 단위 위험요인(low_night_population/crime_rate): 결측 자치구 보정 후 0~1 정규화 확인.
- 안심귀갓길 경로(라인): bbox 밖 경로만 걸러낸다.
"""
from __future__ import annotations

import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from .config import POSITIVE_CATEGORIES, settings

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

GU_RISK_CATEGORIES = {
    "low_night_population": "low_night_population_risk",
    "crime_rate": "crime_rate_risk",
}


def _in_seoul_bbox(df: pd.DataFrame) -> pd.Series:
    return (
        df["lon"].between(settings.bbox_min_lon, settings.bbox_max_lon)
        & df["lat"].between(settings.bbox_min_lat, settings.bbox_max_lat)
    )


def clean_point_facilities() -> pd.DataFrame:
    raw_dir = os.path.join(settings.output_dir, "raw")
    frames = []
    for cat in POSITIVE_CATEGORIES:
        path = os.path.join(raw_dir, f"{cat}.csv")
        if not os.path.exists(path):
            logger.warning("원본 파일 없음, 건너뜀: %s", path)
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")
        before = len(df)

        # 0건 응답이면 헤더만 있는 CSV가 되어 lat/lon이 object dtype으로 읽힘 — round() 전에 변환
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        df = df.dropna(subset=["lat", "lon"])
        df = df[_in_seoul_bbox(df)]
        # 동일 카테고리 + 좌표 소수점 5자리(약 1m) 반올림 기준 중복 제거
        df["_lat_r"] = df["lat"].round(5)
        df["_lon_r"] = df["lon"].round(5)
        df = df.drop_duplicates(subset=["category", "_lat_r", "_lon_r"]).drop(columns=["_lat_r", "_lon_r"])

        after = len(df)
        logger.info("[clean:%s] %d -> %d (결측/범위밖/중복 %d건 제거)", cat, before, after, before - after)
        frames.append(df)

    if not frames:
        raise RuntimeError("정제할 원본 시설 데이터가 없습니다. 먼저 collect.py를 실행하세요.")

    combined = pd.concat(frames, ignore_index=True)
    out_dir = os.path.join(settings.output_dir, "clean")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "facilities_clean.csv")
    combined.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("정제된 시설 데이터 %d건 -> %s", len(combined), out_path)
    return combined


def clean_gu_risk() -> pd.DataFrame:
    raw_dir = os.path.join(settings.output_dir, "raw")
    merged: pd.DataFrame | None = None
    for raw_name, col in GU_RISK_CATEGORIES.items():
        path = os.path.join(raw_dir, f"{raw_name}.csv")
        if not os.path.exists(path):
            logger.warning("원본 파일 없음, 건너뜀: %s", path)
            continue
        df = pd.read_csv(path, encoding="utf-8-sig")[["gu", col]]
        # 0~1 정규화 보정 (이미 정규화되어 있어도 안전하게 재확인)
        df[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min() + 1e-9)
        merged = df if merged is None else merged.merge(df, on="gu", how="outer")

    if merged is None:
        raise RuntimeError("정제할 자치구 단위 위험요인 데이터가 없습니다. 먼저 collect.py를 실행하세요.")

    merged = merged.fillna(merged.mean(numeric_only=True))
    out_dir = os.path.join(settings.output_dir, "clean")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "gu_risk_clean.csv")
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("정제된 자치구 위험요인 데이터 %d개 자치구 -> %s", len(merged), out_path)
    return merged


def clean_safe_route() -> gpd.GeoDataFrame | None:
    raw_path = os.path.join(settings.output_dir, "raw", "safe_route.geojson")
    if not os.path.exists(raw_path):
        logger.warning("원본 파일 없음, 건너뜀: %s", raw_path)
        return None

    gdf = gpd.read_file(raw_path)
    before = len(gdf)
    gdf = gdf[gdf.geometry.notna() & gdf.geometry.is_valid]

    bbox_geom = box(settings.bbox_min_lon, settings.bbox_min_lat, settings.bbox_max_lon, settings.bbox_max_lat)
    gdf = gdf[gdf.intersects(bbox_geom)]
    after = len(gdf)
    logger.info("[clean:safe_route] %d -> %d (유효하지 않거나 범위 밖 경로 %d건 제거)", before, after, before - after)

    out_dir = os.path.join(settings.output_dir, "clean")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "safe_route_clean.geojson")
    gdf.to_file(out_path, driver="GeoJSON")
    logger.info("정제된 안심귀갓길 경로 %d개 -> %s", len(gdf), out_path)
    return gdf


def run_clean() -> tuple[pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame | None]:
    facilities = clean_point_facilities()
    gu_risk = clean_gu_risk()
    routes = clean_safe_route()
    return facilities, gu_risk, routes


if __name__ == "__main__":
    run_clean()
