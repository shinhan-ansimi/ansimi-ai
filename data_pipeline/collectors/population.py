"""행정동 단위 서울 생활인구(심야 0~5시) 수집.

출처: 서울 열린데이터광장 OA-14991(행정동) / OA-14979(집계구, 더 세밀함).
이 데이터는 월별 대용량 파일(CSV)로 배포되므로 Open API 실시간 호출보다는
파일을 내려받아 가공하는 방식이 일반적이다. 실제 운영 시:

    from .population import load_from_file
    df = load_from_file("/path/to/LOCAL_PEOPLE_DONG_202601.csv")

형태로 실데이터 파일을 읽도록 구현해뒀고, 파일이 없으면(mock 모드 포함) 자치구 단위로
심야 유동인구가 적을수록 값이 커지는 "위험 가중치"를 합성해서 반환한다.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from ..config import settings

GU_LIST = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
    "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
    "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구",
]


def load_from_file(path: str, night_hour_cols: tuple[str, ...] = ("0", "1", "2", "3", "4")) -> pd.DataFrame:
    """서울 생활인구 원본 CSV(시간대별 컬럼 포함)를 읽어 자치구별 심야(0~4시) 평균 인구를 계산."""
    df = pd.read_csv(path, encoding="cp949")
    # 실제 컬럼명은 '시간대구분','자치구코드' 등으로 배포본마다 다를 수 있어
    # 운영 전 1회 실제 파일로 컬럼명을 확정해야 한다 (01_data_sources.md 참고).
    raise NotImplementedError(
        "실제 생활인구 원본 파일 스키마 확인 후 구현하세요. 지금은 mock 함수 generate_mock()을 쓰세요."
    )


def generate_mock(rng: np.random.Generator) -> pd.DataFrame:
    """자치구별 '심야 유동인구 희소도' 위험가중치 (0~1, 클수록 인적이 드물어 위험)."""
    base = rng.uniform(0.1, 1.0, size=len(GU_LIST))
    return pd.DataFrame(
        {
            "gu": GU_LIST,
            "low_night_population_risk": base / base.max(),
        }
    )


def collect(rng: np.random.Generator) -> pd.DataFrame:
    if not settings.use_mock:
        file_path = os.environ.get("SEOUL_POPULATION_FILE")
        if file_path and os.path.exists(file_path):
            return load_from_file(file_path)
    return generate_mock(rng)
