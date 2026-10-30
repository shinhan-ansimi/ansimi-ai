"""전체 파이프라인: 수집(1.4) -> 정제(2.1) -> 격자 생성(2.1) -> 스코어링(2.2).

실행:
    cd ansimi-ai
    python -m data_pipeline.pipeline
    python -m data_pipeline.pipeline --cell-size 50   # 격자 크기 바꾸기
"""
from __future__ import annotations

import argparse
import logging

from .clean import run_clean
from .collect import run_collection
from .config import settings
from .grid import run_grid, save_grid
from .scoring import compute_safety_score

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="안심이 위험 데이터 수집-정제-격자 생성 파이프라인")
    parser.add_argument("--cell-size", type=int, default=settings.grid_cell_size_m, help="격자 셀 크기(m)")
    args = parser.parse_args()

    logger.info("=== 1단계: 수집 (mock=%s) ===", settings.use_mock)
    run_collection()

    logger.info("=== 2단계: 정제 ===")
    facilities, gu_risk, routes = run_clean()

    logger.info("=== 3단계: 격자 생성 (%dm) ===", args.cell_size)
    grid = run_grid(facilities, gu_risk, routes, cell_size_m=args.cell_size)

    logger.info("=== 4단계: 규칙 기반 스코어링 ===")
    grid["safety_score"] = compute_safety_score(grid)
    save_grid(grid)  # csv/geojson 둘 다 safety_score 포함해서 다시 저장 (geojson이 구버전으로 남지 않도록)

    logger.info("완료: 총 %d개 격자, safety_score 평균=%.2f, output_dir=%s", len(grid), grid["safety_score"].mean(), settings.output_dir)


if __name__ == "__main__":
    main()
