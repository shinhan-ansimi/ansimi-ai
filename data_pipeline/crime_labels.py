"""생활안전지도 범죄주의구간 WMS(safemap.go.kr)를 LightGBM 학습용 대리 라벨로 변환.

이 WMS는 좌표 목록이 아니라 "도로 위에 등급(1~10)을 색으로 칠한 지도 이미지"를 준다.
그래서: ① 범례(lgdInfo)로 색상(hex) -> 등급 매핑을 받고, ② 서울 bbox 전체를 격자
해상도에 맞춘 이미지 한 장으로 받아서, ③ 픽셀 색을 등급으로 분류한 뒤, ④ 각 격자가
덮는 작은 픽셀 영역에서 가장 높은 등급을 그 격자의 라벨로 쓴다(칸 중심이 정확히
도로선 위에 있는 경우가 드물어서 — maximum_filter로 영역 최댓값을 벡터화해서 처리).
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import urllib.parse

import numpy as np
import pandas as pd
import requests
from PIL import Image
from scipy.ndimage import maximum_filter

from .config import settings
from .grid import add_column_to_outputs

logger = logging.getLogger(__name__)

WMS_ENDPOINT = "https://safemap.go.kr/openapi2/IF_0087_WMS"
LEGEND_ENDPOINT = "https://safemap.go.kr/openapi2/lgdInfo"
LAYER_INT_ID = "IF_0087"

PIXELS_PER_CELL = 2  # 격자 한 칸(100m)이 대략 이만큼의 픽셀이 되도록 해상도를 잡음
_COLOR_MATCH_THRESHOLD = 40  # 이보다 먼 색은 범례색이 아닌 배경/도로로 취급


def fetch_legend(api_key: str) -> dict[tuple[int, int, int], int]:
    """색상(RGB) -> 등급(1~10) 매핑을 받는다."""
    resp = requests.get(LEGEND_ENDPOINT, params={"serviceKey": api_key, "intId": LAYER_INT_ID}, timeout=15)
    resp.raise_for_status()
    items = resp.json()["body"]["items"]["item"]
    mapping: dict[tuple[int, int, int], int] = {}
    for item in items:
        hex_color = item["IMAGE"].lstrip("#")
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        mapping[rgb] = int(item["LGD_NO"])
    return mapping


def _wms_resolution() -> tuple[int, int]:
    """서울 bbox를 PIXELS_PER_CELL px/격자 해상도로 찍을 때 필요한 (width, height)."""
    lat_span = settings.bbox_max_lat - settings.bbox_min_lat
    lon_span = settings.bbox_max_lon - settings.bbox_min_lon
    center_lat = (settings.bbox_min_lat + settings.bbox_max_lat) / 2
    lat_m = lat_span * 111_000
    lon_m = lon_span * 111_000 * np.cos(np.radians(center_lat))
    width = max(int(lon_m / settings.grid_cell_size_m * PIXELS_PER_CELL), 10)
    height = max(int(lat_m / settings.grid_cell_size_m * PIXELS_PER_CELL), 10)
    return width, height


def fetch_wms_image(api_key: str, width: int, height: int) -> np.ndarray:
    """서울 bbox 전체를 RGBA 픽셀 배열로 받는다."""
    params = {
        "serviceKey": api_key,
        "srs": settings.wgs84_crs,
        "bbox": f"{settings.bbox_min_lon},{settings.bbox_min_lat},{settings.bbox_max_lon},{settings.bbox_max_lat}",
        "format": "image/png",
        "width": width,
        "height": height,
        "transparent": "TRUE",
    }
    resp = requests.get(WMS_ENDPOINT, params=params, timeout=60)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    return np.array(img)


def classify_pixels(rgba: np.ndarray, legend: dict[tuple[int, int, int], int]) -> np.ndarray:
    """픽셀별 RGB를 가장 가까운 범례 색에 매칭해 등급(0~10, 0=배경/데이터없음) 배열을 만든다."""
    h, w, _ = rgba.shape
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3]

    legend_colors = np.array(list(legend.keys()), dtype=np.float32)
    legend_grades = np.array(list(legend.values()), dtype=np.uint8)

    flat_rgb = rgb.reshape(-1, 3)
    dists = np.linalg.norm(flat_rgb[:, None, :] - legend_colors[None, :, :], axis=2)
    nearest = dists.argmin(axis=1)
    grade = legend_grades[nearest].reshape(h, w).astype(np.uint8)

    min_dist = dists.min(axis=1).reshape(h, w)
    grade[alpha == 0] = 0
    grade[min_dist > _COLOR_MATCH_THRESHOLD] = 0
    return grade


def extract_grid_labels(grid: pd.DataFrame, api_key: str) -> pd.Series:
    """격자별 crime_hotspot_grade(0~10, 범례 기준 밀도분석 등급) 라벨을 WMS에서 뽑아낸다."""
    legend = fetch_legend(api_key)
    width, height = _wms_resolution()
    logger.info("[crime_labels] WMS 이미지 요청 %dx%d", width, height)
    rgba = fetch_wms_image(api_key, width, height)

    grade = classify_pixels(rgba, legend)
    # 칸 영역만큼(반경 PIXELS_PER_CELL) 최댓값을 퍼뜨려서, 칸 중심이 도로선과
    # 살짝 안 맞아도 그 칸을 지나는 위험 구간을 놓치지 않게 한다.
    dilated = maximum_filter(grade, size=PIXELS_PER_CELL * 2 + 1)

    lat_span = settings.bbox_max_lat - settings.bbox_min_lat
    lon_span = settings.bbox_max_lon - settings.bbox_min_lon
    px = ((grid["center_lon"] - settings.bbox_min_lon) / lon_span * (width - 1)).round().astype(int).clip(0, width - 1)
    py = ((settings.bbox_max_lat - grid["center_lat"]) / lat_span * (height - 1)).round().astype(int).clip(0, height - 1)
    return pd.Series(dilated[py.to_numpy(), px.to_numpy()], index=grid.index, name="crime_hotspot_grade")


def run(grid_csv: str, api_key: str | None = None) -> pd.DataFrame | None:
    """SAFEMAP_CRIME_WMS_KEY가 없으면 조용히 건너뛴다(선택 기능이라 파이프라인을 깨면 안 됨)."""
    api_key = api_key or os.environ.get("SAFEMAP_CRIME_WMS_KEY")
    if not api_key:
        logger.info("[crime_labels] SAFEMAP_CRIME_WMS_KEY 없음 — v2(LightGBM) 라벨 추출 건너뜀")
        return None
    api_key = urllib.parse.unquote(api_key)  # Encoding/Decoding 키 어느 쪽이 들어와도 안전하게

    grid = pd.read_csv(grid_csv, encoding="utf-8-sig")
    grid["crime_hotspot_grade"] = extract_grid_labels(grid, api_key)
    add_column_to_outputs("crime_hotspot_grade", grid.set_index("grid_id")["crime_hotspot_grade"])
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description="범죄주의구간 WMS -> 격자 라벨 추출")
    parser.add_argument("--grid-csv", default=os.path.join(settings.output_dir, "grid", "risk_grid.csv"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    grid = run(args.grid_csv)
    if grid is None:
        return
    logger.info("완료: crime_hotspot_grade 분포\n%s", grid["crime_hotspot_grade"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
