"""CCTV(방범용) 설치 현황 수집.

서울시 CCTV 좌표 API(통합·구별·안심이 연계 전부 포함)는 전부 서비스 종료됐다(2026-10 확인,
보안 이슈로 폐쇄된 것으로 보임). 그래서 **행정안전부 전국 CCTV 표준데이터**(data.go.kr
15013094, 파일 다운로드)를 메인 소스로 쓴다. `CCTV_STANDARD_FILE` 환경변수에 CSV 경로를
지정하면 된다(원본이 76MB+라 서울만 미리 걸러둔 사본 권장).
"""
from __future__ import annotations

import logging
import os
import re

import numpy as np
import pandas as pd

from ..config import settings
from .base import random_points_in_bbox
from .facilities import MOCK_SCALE

logger = logging.getLogger(__name__)

SOURCE = "서울 열린데이터광장 CCTV 설치현황"
STANDARD_SOURCE = "행정안전부 전국 CCTV 표준데이터"

_GU_PATTERN = re.compile(r"([가-힣]+구)")


def load_from_file(path: str) -> pd.DataFrame:
    """행정안전부 전국 CCTV 표준데이터 CSV(data.go.kr 15013094)를 표준 스키마로 변환."""
    try:  # 원본은 cp949, 서울만 걸러둔 사본은 utf-8-sig일 수 있어 둘 다 시도
        df = pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp949")

    def _extract_gu(row: pd.Series) -> str | None:
        for col in ("소재지도로명주소", "소재지지번주소"):
            addr = row.get(col)
            if isinstance(addr, str):
                m = _GU_PATTERN.search(addr)
                if m:
                    return m.group(1)
        return None

    out = pd.DataFrame()
    out["lat"] = pd.to_numeric(df["WGS84위도"], errors="coerce")
    out["lon"] = pd.to_numeric(df["WGS84경도"], errors="coerce")
    out["name"] = df["소재지도로명주소"].fillna(df.get("소재지지번주소"))
    out["gu"] = df.apply(_extract_gu, axis=1)
    out["category"] = "cctv"
    out["source"] = STANDARD_SOURCE
    return out.dropna(subset=["lat", "lon"])


def collect(rng: np.random.Generator) -> pd.DataFrame:
    standard_file = os.environ.get("CCTV_STANDARD_FILE")
    if not settings.use_mock and standard_file and os.path.exists(standard_file):
        df = load_from_file(standard_file)
        logger.info("[cctv] 전국 CCTV 표준데이터 파일에서 %d건 수집", len(df))
        return df

    return random_points_in_bbox(n=MOCK_SCALE["cctv"], category="cctv", source=f"{SOURCE}(mock)", rng=rng)
