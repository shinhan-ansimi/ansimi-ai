"""risk_grid.csv를 메모리에 올려 좌표 기준으로 최근접 격자를 찾는 인덱스."""
from __future__ import annotations

import os

import pandas as pd
from scipy.spatial import cKDTree

from data_pipeline.config import settings

GRID_CSV = os.path.join(settings.output_dir, "grid", "risk_grid.csv")


class GridIndex:
    """risk_grid.csv를 한 번 로드해서 좌표 -> 최근접 격자 조회를 제공한다."""

    def __init__(self, grid_csv: str = GRID_CSV):
        if not os.path.exists(grid_csv):
            raise FileNotFoundError(
                f"{grid_csv} 가 없습니다 — 먼저 `python -m data_pipeline.pipeline` 로 격자를 생성하세요."
            )
        self.df = pd.read_csv(grid_csv, encoding="utf-8-sig")
        if "safety_score" not in self.df.columns:
            raise ValueError(
                "risk_grid.csv에 safety_score 컬럼이 없습니다 — "
                "`python -m data_pipeline.scoring` 을 먼저 실행하세요."
            )
        self.tree = cKDTree(self.df[["center_lon", "center_lat"]].to_numpy())

    def in_coverage(self, lat: float, lon: float) -> bool:
        return (
            settings.bbox_min_lat <= lat <= settings.bbox_max_lat
            and settings.bbox_min_lon <= lon <= settings.bbox_max_lon
        )

    def nearest(self, lat: float, lon: float) -> dict:
        _, idx = self.tree.query([lon, lat], k=1)
        return self.df.iloc[idx].to_dict()
