"""안심이 AI 파트 - 공통 설정.

.env에 키를 채우고 USE_MOCK=0이면 실제 API를 호출하고, 기본값(USE_MOCK=1)이면 mock 데이터를 씁니다.
서울 열린데이터광장은 서비스 신청마다 전용 키가 나와서, 카테고리별로 .env 변수를 따로 둡니다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

# 카테고리 -> .env 변수명. 실제로 get_seoul_key()를 쓰는 수집기만 넣는다(안 쓰면 여기도 지울 것).
SEOUL_KEY_ENV_MAP: dict[str, str] = {
    "security_light": "SEOUL_KEY_SECURITY_LIGHT",
    "route_service": "SEOUL_KEY_SAFE_ROUTE_SERVICE",  # OA-21697
}


def get_seoul_key(category: str) -> str:
    """카테고리 전용 키가 있으면 그걸, 없으면 공용 키(SEOUL_OPENAPI_KEY)로 폴백."""
    env_name = SEOUL_KEY_ENV_MAP.get(category)
    specific = os.environ.get(env_name, "") if env_name else ""
    return specific or os.environ.get("SEOUL_OPENAPI_KEY", "")


@dataclass(frozen=True)
class Settings:
    # --- 인증키 (운영 환경에서 .env 로 주입) ---
    # 카테고리별 키는 get_seoul_key()로 따로 조회한다. 이 필드는 "공용/폴백"키 + 데이터고kr 키만 보관.
    seoul_openapi_key: str = os.environ.get("SEOUL_OPENAPI_KEY", "")  # 카테고리 전용 키가 없을 때 쓰는 폴백 공용키
    data_go_kr_key: str = os.environ.get("DATA_GO_KR_KEY", "")  # 공공데이터포털 공통키 (편의점 상가정보, 경찰관서 등)

    # --- 동작 모드 ---
    # 운영 서버에서는 환경변수 USE_MOCK=0 으로 끄고 실제 키를 넣어서 쓴다.
    use_mock: bool = os.environ.get("USE_MOCK", "1") == "1"

    # --- 대상 지역 (1차 서비스 범위: 서울시 전역 bbox) ---
    # 위경도 기준 서울시 대략 경계 (출처: 서울 열린데이터광장 행정구역 안내)
    bbox_min_lon: float = 126.734
    bbox_max_lon: float = 127.269
    bbox_min_lat: float = 37.413
    bbox_max_lat: float = 37.715

    # --- 서울 열린데이터광장 Open API 공통 패턴 ---
    seoul_api_base: str = "http://openapi.seoul.go.kr:8088"

    # --- 격자 생성 설정 ---
    grid_cell_size_m: int = 100  # 100m x 100m 격자 (2.2 v1 규칙기반 스코어링과 합의된 단위)
    # 좌표 변환용 평면 좌표계: 국토지리정보원 Korea 2000 중부원점(미터 단위, 격자 만들기 좋음)
    projected_crs: str = "EPSG:5181"
    wgs84_crs: str = "EPSG:4326"

    # --- 출력 경로 ---
    output_dir: str = os.environ.get(
        "ANSIMI_OUTPUT_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_pipeline", "output"),
    )

    # mock 데이터 재현성
    random_seed: int = 42


settings = Settings()

# 격자 feature에 쓸 카테고리 정의 (양의 요인: 안전시설 / 음의 요인: 위험요인)
POSITIVE_CATEGORIES = [
    "cctv",
    "security_light",
    "emergency_bell",
    "police",
    "convenience_store",
    # --- 안심귀갓길(OA-21695~97) 연계 카테고리 ---
    "route_cctv",  # 안심귀갓길 구간의 CCTV (OA-21696)
    "route_emergency_bell",  # 안심귀갓길 구간의 안심벨 (OA-21696)
    "route_signage",  # 안심귀갓길 안내표지판 (OA-21696)
    "route_security_light",  # 안심귀갓길 구간의 보안등 (OA-21696)
    "safe_delivery_box",  # 안심택배함 (OA-21697)
    "safe_route_guardian_house",  # 안심귀가길 지킴이집 (OA-21697)
]
NEGATIVE_CATEGORIES = [
    "low_night_population",  # 심야 유동인구 희소 (생활인구 데이터에서 파생, 값이 클수록 위험)
    "crime_rate",  # 자치구 5대범죄 발생률(인구 대비, 구 단위를 격자에 배분)
]
