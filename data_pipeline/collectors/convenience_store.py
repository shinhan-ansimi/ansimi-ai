"""24시 편의점 위치 수집 (야간 영업 안전시설 proxy).

출처: 소상공인시장진흥공단 상가(상권)정보 open API (data.go.kr 15083033).
이 데이터셋은 업종대분류=소매, 업종중분류=편의점 으로 필터링해서 쓴다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .facilities import collect_point_facility

SOURCE = "소상공인시장진흥공단 상가(상권)정보 - 편의점 (data.go.kr 15083033)"
SERVICE_NAME = "storeListInUpjongCode"  # TODO: 실제 발급받은 서비스명으로 교체


def collect(rng: np.random.Generator) -> pd.DataFrame:
    return collect_point_facility("convenience_store", SOURCE, SERVICE_NAME, rng)
