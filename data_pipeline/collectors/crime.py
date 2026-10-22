"""서울시 5대범죄 발생현황 통계 (자치구 단위) 수집.

출처: 서울 열린데이터광장 316(5대범죄 발생현황) / 10943(발생장소별) /
      data.go.kr 15054738(경찰청, 경찰서별 5대범죄 발생·검거 현황).
연 1회 집계 파일로 배포 → 다운로드한 CSV/XLSX를 자치구 단위로 집계해서 쓴다.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from ..config import settings
from .population import GU_LIST


def load_from_file(path: str) -> pd.DataFrame:
    """실제 5대범죄 통계 파일(자치구/경찰서 단위)을 읽어 자치구별 발생건수를 반환.
    경찰서 관할과 행정구역(자치구)이 1:1로 안 맞는 경우가 있어, 매핑 테이블이 필요할 수 있음.
    """
    df = pd.read_excel(path)
    raise NotImplementedError(
        "실제 파일 컬럼 구조 확인 후 자치구별 합계로 집계하는 로직을 채우세요. "
        "지금은 mock 함수 generate_mock()을 쓰세요."
    )


def generate_mock(rng: np.random.Generator) -> pd.DataFrame:
    """자치구별 인구 대비 5대범죄 발생률(0~1 정규화, 클수록 위험)."""
    base = rng.gamma(shape=2.0, scale=1.0, size=len(GU_LIST))
    return pd.DataFrame(
        {
            "gu": GU_LIST,
            "crime_rate_risk": base / base.max(),
        }
    )


def collect(rng: np.random.Generator) -> pd.DataFrame:
    if not settings.use_mock:
        file_path = os.environ.get("SEOUL_CRIME_FILE")
        if file_path and os.path.exists(file_path):
            return load_from_file(file_path)
    return generate_mock(rng)
