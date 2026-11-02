# 안심이 — AI 파트 (1.4 수집 + 2.1 정제·격자 생성 + 2.2 스코어링 + 2.3 API + v2 LightGBM)

간트차트 상 AI 담당 작업 **1.4 위험 데이터 조사·수집**, **2.1 정제·격자 생성**,
**2.2 v1 규칙 가중치 위험도**, **2.3 스코어링 API**를 실제로 돌아가는 파이프라인 +
FastAPI 서버로 구현한 저장소입니다. 서울시 공공데이터(CCTV·보안등·비상벨·안심귀갓길
등)를 수집해 정제하고, 서울 전역을 100m×100m 격자로 나눠 격자별 안전시설 개수·
위험요인을 집계한 뒤, 가중치 기반 공식으로 0~100 안전도 점수(`safety_score`)를
계산하고, 좌표를 넣으면 그 점수를 돌려주는 API(`fastapi_app/`)까지 제공합니다.
간트에는 없던 추가 작업으로, 생활안전지도 범죄주의구간을 대리 라벨 삼은 **LightGBM
기반 v2(참고용)** 도 구현했습니다(`SAFEMAP_CRIME_WMS_KEY` 있을 때만 동작).

## 이 저장소에 올라가는 데이터

코드와 설정 파일만 올라가고, **실제 CSV/SHP 원본 데이터와 `.env`(인증키)는 git에 올라가지
않습니다**(`.gitignore` 처리). 원본 데이터는 각자 로컬의 `data_raw/`에 받아두고 `.env`에
경로/키를 채우는 구조입니다.

카테고리별 실데이터 확보 현황 (2026-10-22 기준):

| 카테고리 | 상태 | 소스 |
|---|---|---|
| CCTV | ✅ 실데이터 | 행정안전부 전국 CCTV 표준데이터 (`CCTV_STANDARD_FILE`) |
| 안심귀갓길 CCTV/안심벨/표지판/보안등 | ✅ 실데이터 | 안심귀갓길 안전시설물 OA-21696 SHP (`ROUTE_FACILITY_SHP`) |
| 안심귀갓길 경로(ground truth) | ✅ 실데이터 | 안심귀갓길 경로 OA-21695 SHP (`SEOUL_SAFE_ROUTE_SHP`) |
| 보안등(서울 전역) | ❌ mock | 서울 열린데이터광장 — 서비스명 미확인 |
| 비상벨(서울 전역) | ❌ mock | 행정안전부 안전비상벨위치정보 API — 현재 서버 오류(HTTP_ERROR) |
| 경찰관서, 편의점 | ❌ mock | 공공데이터포털 — 키 미발급 |
| 안심택배함, 지킴이집 | ❌ mock | 안심귀갓길 서비스 OA-21697 — 파일/키 미확보 |
| 심야 생활인구, 범죄율(자치구 통계) | ❌ mock | 파일 다운로드 방식 — 파일 미확보 |
| 범죄주의구간 등급(LightGBM 학습용 대리 라벨) | ✅ 실데이터 | safemap.go.kr WMS (`SAFEMAP_CRIME_WMS_KEY`) — 위 "범죄율(자치구 통계)"와는 다른 데이터임 |

구별 CCTV 개별 Open API(종로/강북/금천/동작/강서)는 전부 "서비스 종료" 상태를 확인해서
전국 표준데이터로 대체했습니다. 자세한 소스별 조사 내용은 `docs/01_data_sources.md` 참고.

## 디렉터리 구조

```
ansimi-ai/
├── docs/
│   ├── 01_data_sources.md     # 1.4: 조사한 공공데이터 소스 정리 (출처 링크 포함)
│   ├── collection_map.png     # 1.4 결과 시각화 (실데이터 수집 현황, 발표용)
│   └── grid_preview.png       # 2.1 결과 시각화 (격자 생성 결과, 발표용)
├── data_pipeline/
│   ├── config.py               # 인증키(카테고리별)/지역범위/격자크기 등 공통 설정
│   ├── collectors/              # 소스별 수집기 (1.4)
│   │   ├── base.py              # 서울 열린데이터광장/공공데이터포털 공통 호출 유틸 + mock 생성기
│   │   ├── facilities.py        # 포인트형 시설 공통 수집 로직
│   │   ├── cctv.py / security_light.py / emergency_bell.py / police.py / convenience_store.py
│   │   ├── route_facilities.py  # 안심귀갓길 안전시설물(OA-21696) — CCTV/비상벨/보안등/표지판
│   │   ├── route_services.py    # 안심귀갓길 서비스(OA-21697) — 안심택배함/지킴이집
│   │   ├── safe_route.py        # 안심귀갓길 경로(OA-21695) — 라인 geometry
│   │   ├── population.py        # 심야 생활인구(자치구 단위)
│   │   └── crime.py             # 5대범죄 발생현황(자치구 단위)
│   ├── collect.py               # 1.4 실행 진입점 (output/raw/*.csv)
│   ├── clean.py                 # 2.1 정제 (output/clean/*.csv)
│   ├── grid.py                  # 2.1 격자 생성 (output/grid/risk_grid.csv, .geojson)
│   ├── scoring.py               # 2.2 v1 규칙 기반 가중합 스코어링 (safety_score)
│   ├── crime_labels.py          # v2: 범죄주의구간 WMS -> 격자별 crime_hotspot_grade 라벨 추출
│   ├── lightgbm_scoring.py      # v2: LightGBM 학습·예측 (lgbm_predicted_crime_grade)
│   ├── pipeline.py              # collect → clean → grid → scoring → (선택)v2 한번에 실행
│   └── output/                  # 실행 결과물 (git 미추적 — 로컬에서 재생성)
├── data_raw/                    # 다운받은 원본 SHP/CSV (git 미추적, 직접 받아서 채울 것)
├── fastapi_app/                 # 2.3: 스코어링 API
│   ├── main.py                   # FastAPI 앱 — GET /health, GET /score
│   └── score.py                  # risk_grid.csv 로드 + 좌표 기준 최근접 격자 조회(GridIndex)
├── tools/visualize_preview.py   # 1.4/2.1 결과를 발표용 이미지로 저장
└── requirements.txt
```

## 실행 방법

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) mock 데이터로 전체 파이프라인 돌려보기 (기본값)
python -m data_pipeline.pipeline --cell-size 100

# 2) 실제 공공데이터로 돌리기
cp .env.example .env   # 발급받은 키/다운받은 파일 경로를 채워넣기
python -m data_pipeline.pipeline --cell-size 100

# 3) 결과를 발표용 이미지로 저장 (docs/collection_map.png, docs/grid_preview.png)
python3 tools/visualize_preview.py

# 4) 스코어링 API 실행 (risk_grid.csv에 safety_score가 있어야 함 — 파이프라인 먼저 실행)
uvicorn fastapi_app.main:app --reload
curl "http://127.0.0.1:8000/score?lat=37.5665&lon=126.9780"
```

`.env.example`에 채워야 할 키/파일 경로가 전부 정리돼 있습니다. 카테고리 하나가 비어있으면
그 카테고리만 mock으로 자동 대체되고 나머지는 정상 진행됩니다.

`SAFEMAP_CRIME_WMS_KEY`가 `.env`에 있으면 파이프라인이 마지막에 v2(LightGBM) 단계까지
자동으로 돌립니다. macOS에서 LightGBM을 처음 쓰면 `brew install libomp`가 추가로
필요합니다(OpenMP 런타임 — 없으면 `import lightgbm`에서 바로 에러가 남).

## 격자(2.1) 설계 메모

- 격자 단위: 기본 **100m x 100m**, 평면좌표계는 `EPSG:5181`(Korea 2000 중부원점, 미터 단위)로
  투영해서 만들고 결과는 다시 WGS84로 되돌려 저장합니다.
- 격자별 feature (`risk_grid.csv` 컬럼):
  - 안전시설 카운트 11종: `cctv_count`, `security_light_count`, `emergency_bell_count`,
    `police_count`, `convenience_store_count`, `route_cctv_count`, `route_emergency_bell_count`,
    `route_signage_count`, `route_security_light_count`, `safe_delivery_box_count`,
    `safe_route_guardian_house_count`
  - 위험요인 2종(자치구 단위에서 격자로 배분): `low_night_population_risk`, `crime_rate_risk` (둘 다 0~1)
  - 공식 안심귀갓길(OA-21695) 관련: `on_safe_route`(0/1), `dist_to_safe_route_m` — 2.2 점수의
    ground truth 검증용 (입력 feature로 쓰지 말 것)
  - 중심 좌표: `center_lat`, `center_lon`
- **알려진 한계**: 자치구 배분이 "격자 중심에서 가장 가까운 안전시설 포인트의 자치구"로 근사돼
  있습니다(`grid.py`의 `assign_gu_nearest`). 운영 전에는 자치구 경계 폴리곤으로
  point-in-polygon(`geopandas.sjoin`)으로 바꾸는 걸 권장합니다.

## 스코어링(2.2) 설계 메모

- `data_pipeline/scoring.py` — `risk_grid.csv`의 안전시설 카운트를 정규화(상위 1% 클립 후
  min-max) 후 `DEFAULT_WEIGHTS`로 가중합해서 0~100 `safety_score` 컬럼을 만듭니다
  (높을수록 안전 — "risk"가 아니라 "safety" 점수입니다).
- 서울 전역 API 데이터와 안심귀갓길 연계분은 같은 신호로 보고 합산합니다
  (`POSITIVE_GROUPS` 참고, 예: `cctv_count` + `route_cctv_count`).
- 가중치는 v1 기본값이라 사람이 정한 1차 판단입니다. 조정하려면 `DEFAULT_WEIGHTS` 숫자만
  바꾸면 됩니다 — 학습 로직이 없어서 재학습 과정이 필요 없습니다.
- 검증: `on_safe_route=1`(공식 안심귀갓길 구간) 격자의 평균 점수가 그 외보다 유의미하게
  높은지 확인합니다(`python -m data_pipeline.scoring` 실행 시 자동 출력 + assert).

## 스코어링 API(2.3) 설계 메모

- `fastapi_app/score.py`의 `GridIndex`가 서버 기동 시 `risk_grid.csv`를 한 번 메모리에
  올리고, `scipy.spatial.cKDTree`로 좌표 기준 최근접 격자를 빠르게 찾습니다(격자 생성 때와
  같은 방식, `grid.py`의 `assign_gu_nearest` 참고).
- `GET /score?lat=&lon=` — 가장 가까운 격자의 `safety_score`, `on_safe_route`,
  격자 중심 좌표를 반환합니다. 좌표가 서울 bbox(`config.settings`) 밖이면 400,
  파라미터가 없거나 범위를 벗어나면(위도 -90~90 등) 422를 반환합니다.
- `GET /health` — 격자가 몇 개 로드됐는지 확인용.
- 지금은 파일(csv)을 매번 서버 기동 시 메모리로 읽는 구조입니다. 데이터가 자주 갱신되거나
  여러 서버 인스턴스가 떠야 하면 PostGIS 테이블로 옮기고 `GridIndex`를 쿼리 기반으로
  바꾸는 걸 고려하세요(지금 구조로는 과한 설계라 넣지 않았습니다).

## v2 LightGBM 설계 메모 (간트차트에 없던 추가 작업, Should)

- **왜 필요했나**: v1(규칙 기반) 가중치는 사람이 정한 값이라 "진짜 위험한 곳"과 맞는지
  검증할 기준이 없었습니다. 그래서 실제 경찰청 데이터(범죄주의구간 등급)를 대리 라벨 삼아
  학습 모델을 만들어 v1과 비교해볼 수 있게 했습니다.
- **라벨 추출이 까다로운 이유**: `crime_labels.py`가 쓰는 safemap.go.kr WMS는 "좌표 목록"이
  아니라 "도로 위에 등급을 색칠한 지도 이미지"를 줍니다. 그래서 ① 범례(색→등급) 조회 →
  ② 격자 해상도에 맞춘 이미지 한 장 요청 → ③ 픽셀 색을 등급으로 분류 →
  ④ 격자별로 주변 픽셀 중 최댓값을 `scipy.ndimage.maximum_filter`로 뽑아 라벨로 쓰는
  과정을 거칩니다(칸 중심이 정확히 도로선 위에 있는 경우가 드물어서, 칸 전체 영역에서
  최댓값을 찾습니다).
- **⚠️ 중요한 해석 주의사항**: `on_safe_route=1`(공식 안심귀갓길) 구간이 `crime_hotspot_grade`
  평균 6.18로, 그 외 구간(1.80)보다 오히려 높게 나옵니다. 버그가 아니라 실제 도시계획
  패턴입니다 — 지자체가 원래 위험했던 곳에 CCTV·보안등을 설치해 안심귀갓길로 지정하기
  때문입니다. 그래서 LightGBM의 feature importance 1위가 `dist_to_safe_route_m`이고,
  "시설이 많을수록 위험하다고 예측"하는 것처럼 보일 수 있는데, 이는 "전반적 안전도"가
  아니라 "현재 시설 배치 패턴을 봤을 때 범죄주의구간일 가능성"을 학습한 것으로 해석해야
  합니다.
- **`low_night_population_risk`/`crime_rate_risk`가 feature importance 상위권인 이유**:
  이 두 컬럼은 아직 **mock 데이터**입니다(위 데이터 현황 표 참고). 지금 보이는 중요도는
  자치구 단위에서 우연히 상관된 노이즈일 가능성이 커서, 실데이터로 교체되기 전까지는
  이 모델의 feature importance를 액면 그대로 믿지 마세요.
- v1(`safety_score`)은 그대로 두고, v2 결과는 `crime_hotspot_grade`(실측 라벨)와
  `lgbm_predicted_crime_grade`(예측값) 두 컬럼으로 risk_grid에 추가만 합니다 — 대체가
  아니라 비교·참고용입니다.
- `SAFEMAP_CRIME_WMS_KEY`가 없으면 이 단계 전체를 조용히 건너뛰고, v1까지는 정상
  동작합니다(`pipeline.py`에서 try/except로 감싸서 v2 실패가 v1 결과에 영향 없음).
