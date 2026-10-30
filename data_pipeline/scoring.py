"""2.2 v1 규칙 가중치 위험도 스코어링.

risk_grid.csv의 안전시설/위험요인 컬럼을 정규화한 뒤 가중합해서 0~100 안전도 점수를 만든다.
학습 없는 규칙 기반(v1) — 가중치는 사람이 정한 값이고, 나중에 LightGBM(v2) 등으로 바뀔 수 있다.
점수는 "risk"가 아니라 "safety"다: 높을수록 안전(CCTV·보안등 많음, 범죄율 낮음).
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .config import settings

# 격자 컬럼 -> 점수에 쓸 feature. 서울 전역 API와 안심귀갓길 연계분은 같은 신호라 합산한다.
POSITIVE_GROUPS: dict[str, list[str]] = {
    "cctv": ["cctv_count", "route_cctv_count"],
    "security_light": ["security_light_count", "route_security_light_count"],
    "emergency_bell": ["emergency_bell_count", "route_emergency_bell_count"],
    "police": ["police_count"],
    "convenience_store": ["convenience_store_count"],
    "signage": ["route_signage_count"],
    "safe_delivery_box": ["safe_delivery_box_count"],
    "safe_route_guardian_house": ["safe_route_guardian_house_count"],
}
NEGATIVE_COLUMNS = ["low_night_population_risk", "crime_rate_risk"]

# v1 기본 가중치 — 1차 판단값, 실데이터/피드백 쌓이면 조정할 것
DEFAULT_WEIGHTS: dict[str, float] = {
    "cctv": 1.5,
    "security_light": 1.2,
    "emergency_bell": 1.0,
    "police": 1.5,
    "convenience_store": 0.8,
    "signage": 0.5,
    "safe_delivery_box": 0.3,
    "safe_route_guardian_house": 0.5,
    "low_night_population_risk": 1.5,
    "crime_rate_risk": 2.0,
}


def _normalize(series: pd.Series) -> pd.Series:
    """상위 1%를 클립한 뒤 0~1 min-max 정규화 (CCTV 등 극단값이 점수를 과도하게 끌지 않도록)."""
    capped = series.clip(upper=series.quantile(0.99))
    lo, hi = capped.min(), capped.max()
    if hi - lo < 1e-9:
        return pd.Series(0.0, index=series.index)
    return (capped - lo) / (hi - lo)


def compute_safety_score(grid: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    weights = weights or DEFAULT_WEIGHTS
    raw = pd.Series(0.0, index=grid.index)

    for feature, cols in POSITIVE_GROUPS.items():
        total = grid[cols].sum(axis=1)
        raw += weights.get(feature, 0.0) * _normalize(total)

    for col in NEGATIVE_COLUMNS:
        raw -= weights.get(col, 0.0) * grid[col].fillna(0)

    lo, hi = raw.min(), raw.max()
    if hi - lo < 1e-9:
        return pd.Series(50.0, index=grid.index)
    return ((raw - lo) / (hi - lo) * 100).round(2)


def run(grid_csv: str, out_csv: str | None = None) -> pd.DataFrame:
    grid = pd.read_csv(grid_csv, encoding="utf-8-sig")
    grid["safety_score"] = compute_safety_score(grid)
    out_csv = out_csv or grid_csv
    grid.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description="2.2 규칙 기반 안전도 스코어링")
    parser.add_argument("--grid-csv", default=os.path.join(settings.output_dir, "grid", "risk_grid.csv"))
    args = parser.parse_args()

    grid = run(args.grid_csv)

    on_route = grid.loc[grid.get("on_safe_route", 0) == 1, "safety_score"].mean()
    off_route = grid.loc[grid.get("on_safe_route", 0) == 0, "safety_score"].mean()
    print(f"완료: {len(grid)}개 격자, safety_score 평균={grid['safety_score'].mean():.2f}")
    print(f"검증: on_safe_route 평균={on_route:.2f} vs 그 외 평균={off_route:.2f}")
    assert on_route > off_route, "안심귀갓길 구간 점수가 그 외보다 낮음 — 가중치/정규화 점검 필요"


if __name__ == "__main__":
    main()
