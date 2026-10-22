"""
수집기 공통 유틸.

- fetch_seoul_openapi: 서울 열린데이터광장 Open API 공통 호출 (페이지네이션 포함)
- fetch_data_go_kr: 공공데이터포털(data.go.kr) 공통 호출 (serviceKey 방식)
- random_points_in_bbox: mock 모드에서 쓰는 지리적으로 그럴듯한 샘플 포인트 생성기
"""
from __future__ import annotations

import time
import urllib.parse
from typing import Any

import numpy as np
import pandas as pd
import requests

from ..config import settings

SEOUL_PAGE_SIZE = 1000


def fetch_seoul_openapi(service_name: str, api_key: str, max_rows: int = 5000) -> list[dict[str, Any]]:
    """서울 열린데이터광장 Open API 공통 호출.

    URL 패턴: http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/
    한 번에 최대 1000행이라 페이지네이션 돌면서 모은다.

    서울 열린데이터광장은 "Open API 서비스 신청"마다 전용 키를 발급하는 구조라,
    호출할 서비스(service_name)에 맞는 키(api_key)를 호출하는 쪽에서 넘겨줘야 한다
    (config.get_seoul_key(category) 로 조회). 공용 키 하나로 통일했다면 그 값을 그대로 넘기면 된다.

    실제 서비스 환경(.env에 키 설정)에서만 의미 있게 동작한다.
    이 샌드박스는 해당 호스트로 나가는 네트워크가 막혀 있어 호출 시 예외가 나며,
    그 경우 상위 수집기가 mock 데이터로 대체한다.
    """
    if not api_key:
        raise RuntimeError(
            f"'{service_name}' 서비스용 인증키가 설정되어 있지 않습니다. "
            "https://data.seoul.go.kr 에서 해당 서비스로 Open API 신청 후 발급받은 키를 "
            ".env에 넣어주세요 (config.py의 SEOUL_KEY_ENV_MAP 참고)."
        )

    rows: list[dict[str, Any]] = []
    start = 1
    while start <= max_rows:
        end = min(start + SEOUL_PAGE_SIZE - 1, max_rows)
        url = f"{settings.seoul_api_base}/{api_key}/json/{service_name}/{start}/{end}/"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        # 서울 열린데이터광장은 최상위 키가 서비스명과 같은 경우가 많음
        body = payload.get(service_name) or next(iter(payload.values()))
        result = body.get("RESULT", {}) if isinstance(body, dict) else {}
        code = result.get("CODE")
        if code not in (None, "INFO-000"):
            if code == "INFO-200":
                # "해당하는 데이터가 없습니다" — 정상적인 빈 결과(마지막 페이지 등)
                break
            # 그 외(ERROR-300번대 인증키 오류, INFO-100 파라미터 오류 등)는 진짜 실패.
            # 여기서 조용히 break하면 호출부가 "실제로 0건 수집"으로 착각해서 mock으로
            # 안 넘어가니, 반드시 예외를 던져서 상위 수집기가 mock으로 폴백하게 한다.
            raise RuntimeError(f"서울 열린데이터광장 API 오류 [{code}] {result.get('MESSAGE', '')} (service={service_name})")

        page_rows = body.get("row", []) if isinstance(body, dict) else []
        if not page_rows:
            break
        rows.extend(page_rows)

        if len(page_rows) < SEOUL_PAGE_SIZE:
            break
        start += SEOUL_PAGE_SIZE
        time.sleep(0.1)  # 과도한 연속 호출 방지

    return rows


def fetch_data_go_kr(
    endpoint: str,
    extra_params: dict[str, Any] | None = None,
    max_rows: int = 5000,
    api_key: str | None = None,
    num_of_rows: int = 1000,
) -> list[dict[str, Any]]:
    """공공데이터포털(data.go.kr) REST API 공통 호출 (serviceKey / pageNo / numOfRows 방식).

    api_key를 안 넘기면 공용 DATA_GO_KR_KEY를 쓴다. 일부 서비스는 한 페이지 최대 건수가
    1000보다 작을 수 있어(예: 안전비상벨위치정보 조회서비스는 max 100) num_of_rows로 맞춘다.
    """
    # data.go.kr은 키를 Encoding/Decoding 두 버전으로 주는데, requests가 params 값을
    # 다시 인코딩하므로 Encoding 키를 그대로 넣으면 이중 인코딩되어 깨진다 — 먼저 디코딩.
    key = urllib.parse.unquote(api_key or settings.data_go_kr_key)
    if not key:
        raise RuntimeError(
            "data.go.kr 서비스키가 설정되어 있지 않습니다. "
            "https://www.data.go.kr 에서 활용신청 후 승인된 서비스키를 환경변수로 넣어주세요."
        )

    rows: list[dict[str, Any]] = []
    page_no = 1
    params = {
        "serviceKey": key,
        "numOfRows": num_of_rows,
        "type": "json",
        **(extra_params or {}),
    }
    while (page_no - 1) * num_of_rows < max_rows:
        params["pageNo"] = page_no
        resp = requests.get(endpoint, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        # 게이트웨이 레벨 오류는 "response.header"가 아니라 별도 envelope로 옴 (서비스별 오류와 포맷이 다름)
        gateway_err = payload.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader")
        if gateway_err:
            raise RuntimeError(f"data.go.kr 게이트웨이 오류 [{gateway_err.get('returnReasonCode')}] {gateway_err.get('returnAuthMsg')} (endpoint={endpoint})")

        header = payload.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        # "00" 외 코드는 진짜 오류라 예외로 던진다 (빈 결과로 착각해 mock 전환을 놓치지 않도록)
        if result_code is not None and result_code not in ("00", "0"):
            raise RuntimeError(f"data.go.kr API 오류 [{result_code}] {header.get('resultMsg', '')} (endpoint={endpoint})")

        items = (
            payload.get("response", {})
            .get("body", {})
            .get("items", {})
        )
        page_rows = items.get("item", []) if isinstance(items, dict) else items
        if not page_rows:
            break
        if isinstance(page_rows, dict):
            page_rows = [page_rows]
        rows.extend(page_rows)
        if len(page_rows) < num_of_rows:
            break
        page_no += 1
        time.sleep(0.1)

    return rows


def random_points_in_bbox(
    n: int,
    category: str,
    source: str,
    rng: np.random.Generator,
    cluster_centers: int = 12,
    cluster_std_deg: float = 0.02,
) -> pd.DataFrame:
    """mock 모드: 완전 균일 난수 대신, 번화가/역세권처럼 몇 개 클러스터 주변에
    모이는 형태로 샘플 포인트를 생성한다 (실제 안전시설 분포가 역세권에 몰리는 특성을 흉내).
    """
    min_lon, max_lon = settings.bbox_min_lon, settings.bbox_max_lon
    min_lat, max_lat = settings.bbox_min_lat, settings.bbox_max_lat

    centers_lon = rng.uniform(min_lon, max_lon, size=cluster_centers)
    centers_lat = rng.uniform(min_lat, max_lat, size=cluster_centers)

    chosen = rng.integers(0, cluster_centers, size=n)
    lon = rng.normal(centers_lon[chosen], cluster_std_deg)
    lat = rng.normal(centers_lat[chosen], cluster_std_deg * 0.8)
    lon = np.clip(lon, min_lon, max_lon)
    lat = np.clip(lat, min_lat, max_lat)

    gu_list = [
        "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구",
        "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구",
        "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구",
    ]
    gu = rng.choice(gu_list, size=n)

    return pd.DataFrame(
        {
            "source": source,
            "category": category,
            "name": [f"{category}_{i:05d}" for i in range(n)],
            "lat": lat,
            "lon": lon,
            "gu": gu,
        }
    )
