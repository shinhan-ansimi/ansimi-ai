"""v2 — LightGBM으로 crime_hotspot_grade(WMS 대리 라벨)를 예측.

v1(data_pipeline/scoring.py)은 사람이 정한 가중치로 계산하는 규칙 기반 점수였고,
이건 실제 범죄주의구간 등급을 정답(y) 삼아 학습하는 지도학습 버전(v2, Should)이다.
v1을 대체하지 않고 risk_grid에 별도 컬럼(lgbm_predicted_crime_grade)으로 추가한다.

주의할 점: 안심귀갓길 구간은 CCTV·보안등이 많으면서 동시에 crime_hotspot_grade도 높게
나온다(지자체가 원래 위험했던 곳에 안전시설을 설치하기 때문) — 그래서 "시설이 많을수록
더 위험하다고 예측"하는 모델이 나올 수 있는데, 이건 버그가 아니라 실제 도시계획 패턴이다.
이 모델은 "전반적 안전도"가 아니라 "현재 시설 배치를 봤을 때 범죄주의구간일 가능성"을
예측하는 것으로 해석해야 한다.
"""
from __future__ import annotations

import argparse
import logging

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from .config import settings
from .grid import add_column_to_outputs

logger = logging.getLogger(__name__)

# 격자 식별자/좌표/타깃 자체는 feature로 안 쓴다. safety_score는 v1 자체 출력이라 제외
# (circular). lgbm_predicted_crime_grade는 이 모듈이 이전에 저장한 자기 자신의 예측값이라
# 반드시 제외해야 함 — 안 그러면 재실행할 때마다 자기 예측을 입력으로 학습하는 데이터 누수가 됨.
# dist_to_safe_route_m은 포함 — 실제로 유용한 공간 신호라 feature로 쓸만함.
TARGET_COLUMN = "crime_hotspot_grade"
PREDICTION_COLUMN = "lgbm_predicted_crime_grade"
EXCLUDE_COLUMNS = {
    "grid_id", "gu", "center_lat", "center_lon", "geometry",
    "safety_score", TARGET_COLUMN, PREDICTION_COLUMN,
}


def _feature_columns(grid: pd.DataFrame) -> list[str]:
    return [c for c in grid.columns if c not in EXCLUDE_COLUMNS and pd.api.types.is_numeric_dtype(grid[c])]


def train(grid: pd.DataFrame, random_state: int = 42) -> tuple[lgb.LGBMRegressor, pd.DataFrame]:
    if TARGET_COLUMN not in grid.columns:
        raise ValueError(
            f"{TARGET_COLUMN} 컬럼이 없습니다 — 먼저 `python -m data_pipeline.crime_labels` 로 라벨을 추출하세요."
        )

    features = _feature_columns(grid)
    X = grid[features].fillna(0)
    y = grid[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=random_state)

    model = lgb.LGBMRegressor(random_state=random_state, verbosity=-1)
    model.fit(X_train, y_train)

    pred_test = model.predict(X_test)
    mae = mean_absolute_error(y_test, pred_test)
    logger.info("검증(held-out 20%%): MAE=%.3f (등급 0~10 스케일)", mae)

    importance = pd.DataFrame({"feature": features, "importance": model.feature_importances_}).sort_values(
        "importance", ascending=False
    )
    logger.info("feature importance 상위 5개:\n%s", importance.head(5).to_string(index=False))

    return model, importance


def run(grid_csv: str) -> pd.DataFrame:
    grid = pd.read_csv(grid_csv, encoding="utf-8-sig")
    model, _ = train(grid)
    features = _feature_columns(grid)
    pred = model.predict(grid[features].fillna(0)).clip(0, 10)  # 등급은 0~10 범위, 회귀 예측은 경계 밖으로 나갈 수 있어 clip
    grid[PREDICTION_COLUMN] = pred.round(2)
    add_column_to_outputs(PREDICTION_COLUMN, grid.set_index("grid_id")[PREDICTION_COLUMN])
    return grid


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description="v2 LightGBM 범죄주의구간 등급 예측")
    parser.add_argument("--grid-csv", default=os.path.join(settings.output_dir, "grid", "risk_grid.csv"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    grid = run(args.grid_csv)
    logger.info("완료: lgbm_predicted_crime_grade 추가, 평균=%.2f", grid["lgbm_predicted_crime_grade"].mean())


if __name__ == "__main__":
    main()
