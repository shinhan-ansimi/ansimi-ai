"""2.1 격자 생성 — 서울 전역을 지정 크기(기본 100m) 격자로 나누고,
정제된 안전시설/위험요인 데이터를 각 격자에 집계해 붙인다.

출력: output/grid/risk_grid.geojson, output/grid/risk_grid.csv
      (risk_grid.csv 는 2.2 "v1 규�칙 가중치 위험도" 단계에서 바로 읽어 쓸 수 있는 형태)
"""
from __future__ import annotations

import logging
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import box

from .config import POSITIVE_CATEGORIES, settings

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _facilities_to_gdf(facilities: pd.DataFrame) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        facilities,
        geometry=gpd.points_from_xy(facilities["lon"], facilities["lat"]),
        crs=settings.wgs84_crs,
    )
    return gdf.to_crs(settings.projected_crs)


def build_fishnet(cell_size_m: int | None = None) -> gpd.GeoDataFrame:
    """서울 bbox(위경도)를 미터 단위 평면좌표계로 투영한 뒤 cell_size_m 간격 격자를 만든다."""
    cell_size_m = cell_size_m or settings.grid_cell_size_m

    bbox_wgs84 = gpd.GeoDataFrame(
        {"id": [0]}, geometry=[box(settings.bbox_min_lon, settings.bbox_min_lat, settings.bbox_max_lon, settings.bbox_max_lat)]
    , crs=settings.wgs84_crs)
    bbox_proj = bbox_wgs84.to_crs(settings.projected_crs)
    minx, miny, maxx, maxy = bbox_proj.total_bounds

    xs = np.arange(minx, maxx, cell_size_m)
    ys = np.arange(miny, maxy, cell_size_m)

    polys = []
    for x in xs:
        for y in ys:
            polys.append(box(x, y, x + cell_size_m, y + cell_size_m))

    grid = gpd.GeoDataFrame({"grid_id": range(len(polys))}, geometry=polys, crs=settings.projected_crs)
    logger.info("격자 생성: %d x %d m 셀, 총 %d개", cell_size_m, cell_size_m, len(grid))
    return grid


def assign_gu_nearest(grid_centroids_proj: gpd.GeoSeries, facilities_gdf: gpd.GeoDataFrame) -> np.ndarray:
    """각 격자 중심점에 가장 가까운 안전시설 포인트의 '자치구' 값을 붙인다.

    (실제 운영 환경에서는 행정안전부/SGIS에서 받은 자치구 경계 폴리곤으로
     sjoin(point-in-polygon)을 쓰는 게 정석이다. 이 샌드박스는 경계 폴리곤 파일이 없어서
     최근접 포인트 방식으로 근사했다 — README에 명시.)
    """
    pts = facilities_gdf[facilities_gdf["gu"].notna()]
    if pts.empty:
        return np.array([None] * len(grid_centroids_proj))

    tree = cKDTree(np.c_[pts.geometry.x, pts.geometry.y])
    query = np.c_[grid_centroids_proj.x, grid_centroids_proj.y]
    _, idx = tree.query(query, k=1)
    return pts["gu"].to_numpy()[idx]


def assign_route_features(
    grid: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame | None,
    on_route_threshold_m: float = 15.0,
) -> pd.DataFrame:
    """격자 중심점마다 가장 가까운 안심귀갓길(OA-21695) 경로까지 거리를 구하고,
    threshold(기본 15m, 도로 폭 감안) 안이면 '공식 안심귀갓길 구간'으로 표시한다.
    """
    if routes is None or routes.empty:
        return pd.DataFrame({"grid_id": grid["grid_id"], "dist_to_safe_route_m": np.nan, "on_safe_route": 0})

    routes_proj = routes.to_crs(settings.projected_crs)
    centroids = gpd.GeoDataFrame(
        {"grid_id": grid["grid_id"]}, geometry=grid.geometry.centroid, crs=settings.projected_crs
    )
    nearest = gpd.sjoin_nearest(
        centroids, routes_proj[["geometry"]], distance_col="dist_to_safe_route_m"
    )
    nearest = nearest.drop_duplicates(subset="grid_id")[["grid_id", "dist_to_safe_route_m"]]
    nearest["on_safe_route"] = (nearest["dist_to_safe_route_m"] <= on_route_threshold_m).astype(int)
    return nearest


def aggregate_grid(
    grid: gpd.GeoDataFrame,
    facilities: pd.DataFrame,
    gu_risk: pd.DataFrame,
    routes: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    facilities_gdf = _facilities_to_gdf(facilities)

    # 격자 중심점(투영 좌표) 먼저 계산 — gu 매칭용
    grid = grid.copy()
    centroids_proj = grid.geometry.centroid

    joined = gpd.sjoin(facilities_gdf, grid[["grid_id", "geometry"]], how="left", predicate="within")
    counts = (
        joined.groupby(["grid_id", "category"]).size().unstack(fill_value=0).reindex(columns=POSITIVE_CATEGORIES, fill_value=0)
    )
    counts = counts.add_suffix("_count").reset_index()

    grid = grid.merge(counts, on="grid_id", how="left")
    for cat in POSITIVE_CATEGORIES:
        col = f"{cat}_count"
        if col not in grid.columns:
            grid[col] = 0
        grid[col] = grid[col].fillna(0).astype(int)

    grid["gu"] = assign_gu_nearest(centroids_proj, facilities_gdf)
    grid = grid.merge(gu_risk, on="gu", how="left")

    route_features = assign_route_features(grid, routes)
    grid = grid.merge(route_features, on="grid_id", how="left")
    grid["on_safe_route"] = grid["on_safe_route"].fillna(0).astype(int)

    # 위경도 중심점(지도/프론트에 쓰기 좋은 형태)
    centroids_wgs84 = grid.geometry.centroid.to_crs(settings.wgs84_crs)
    grid["center_lon"] = centroids_wgs84.x
    grid["center_lat"] = centroids_wgs84.y

    return grid


def save_grid(grid: gpd.GeoDataFrame) -> tuple[str, str]:
    out_dir = os.path.join(settings.output_dir, "grid")
    os.makedirs(out_dir, exist_ok=True)

    geojson_path = os.path.join(out_dir, "risk_grid.geojson")
    grid.to_crs(settings.wgs84_crs).to_file(geojson_path, driver="GeoJSON")

    csv_path = os.path.join(out_dir, "risk_grid.csv")
    grid.drop(columns="geometry").to_csv(csv_path, index=False, encoding="utf-8-sig")

    logger.info("격자 결과 저장: %s (%d개 셀), %s", geojson_path, len(grid), csv_path)
    return geojson_path, csv_path


def run_grid(
    facilities: pd.DataFrame,
    gu_risk: pd.DataFrame,
    routes: gpd.GeoDataFrame | None = None,
    cell_size_m: int | None = None,
) -> gpd.GeoDataFrame:
    grid = build_fishnet(cell_size_m)
    grid = aggregate_grid(grid, facilities, gu_risk, routes)
    save_grid(grid)
    return grid


if __name__ == "__main__":
    facilities = pd.read_csv(os.path.join(settings.output_dir, "clean", "facilities_clean.csv"), encoding="utf-8-sig")
    gu_risk = pd.read_csv(os.path.join(settings.output_dir, "clean", "gu_risk_clean.csv"), encoding="utf-8-sig")
    routes_path = os.path.join(settings.output_dir, "clean", "safe_route_clean.geojson")
    routes = gpd.read_file(routes_path) if os.path.exists(routes_path) else None
    run_grid(facilities, gu_risk, routes)
