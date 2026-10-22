"""1.4 위험 데이터 조사·수집 — 전체 수집기를 돌려서 output/raw/ 에 저장."""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from .collectors import (
    cctv,
    convenience_store,
    crime,
    emergency_bell,
    police,
    population,
    route_facilities,
    route_services,
    safe_route,
    security_light,
)
from .config import settings

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 카테고리 하나 = 파일 하나로 끝나는 "단일 카테고리" 수집기
SINGLE_CATEGORY_COLLECTORS = {
    "cctv": cctv.collect,
    "security_light": security_light.collect,
    "emergency_bell": emergency_bell.collect,
    "police": police.collect,
    "convenience_store": convenience_store.collect,
}

# 한 번 호출하면 여러 카테고리가 섞여 나오는 수집기 (호출 후 category 컬럼 기준으로 쪼갠다)
MULTI_CATEGORY_COLLECTORS = {
    "route_facilities": route_facilities.collect,  # -> route_cctv / route_emergency_bell / route_signage
    "route_services": route_services.collect,  # -> safe_delivery_box / safe_route_guardian_house
}

GU_LEVEL_COLLECTORS = {
    "low_night_population": population.collect,
    "crime_rate": crime.collect,
}


def run_collection() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(settings.random_seed)
    raw_dir = os.path.join(settings.output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    results: dict[str, pd.DataFrame] = {}

    for name, fn in SINGLE_CATEGORY_COLLECTORS.items():
        df = fn(rng)
        results[name] = df
        out_path = os.path.join(raw_dir, f"{name}.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        logger.info("%s: %d건 -> %s", name, len(df), out_path)

    for group_name, fn in MULTI_CATEGORY_COLLECTORS.items():
        combined = fn(rng)
        for cat, sub in combined.groupby("category"):
            results[cat] = sub
            out_path = os.path.join(raw_dir, f"{cat}.csv")
            sub.to_csv(out_path, index=False, encoding="utf-8-sig")
            logger.info("%s (%s): %d건 -> %s", cat, group_name, len(sub), out_path)

    for name, fn in GU_LEVEL_COLLECTORS.items():
        df = fn(rng)
        results[name] = df
        out_path = os.path.join(raw_dir, f"{name}.csv")
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        logger.info("%s: %d건(자치구 단위) -> %s", name, len(df), out_path)

    # 안심귀갓길 "경로"는 포인트가 아니라 라인이라 별도 geojson으로 저장
    routes = safe_route.collect(rng)
    routes_path = os.path.join(raw_dir, "safe_route.geojson")
    routes.to_file(routes_path, driver="GeoJSON")
    logger.info("safe_route: %d개 경로 -> %s", len(routes), routes_path)

    return results


if __name__ == "__main__":
    run_collection()
