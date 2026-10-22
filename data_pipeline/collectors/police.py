"""경찰관서(지구대/파출소) 위치 수집. 최단거리를 '출동 반경' proxy로 사용."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .facilities import collect_point_facility

SOURCE = "경찰청 전국 지구대·파출소 위치"
SERVICE_NAME = "SearchSTNBySidoServiceKey"  # TODO: 실제 발급받은 서비스명으로 교체


def collect(rng: np.random.Generator) -> pd.DataFrame:
    return collect_point_facility("police", SOURCE, SERVICE_NAME, rng)
