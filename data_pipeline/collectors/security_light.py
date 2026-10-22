"""보안등(가로등) 설치 위치 수집. 야간 조도(밝기)의 proxy로 사용."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .facilities import collect_point_facility

SOURCE = "서울 열린데이터광장 보안등 설치현황"
SERVICE_NAME = "TbSecurityLampInfo"  # TODO: 실제 발급받은 서비스명으로 교체


def collect(rng: np.random.Generator) -> pd.DataFrame:
    return collect_point_facility("security_light", SOURCE, SERVICE_NAME, rng)
