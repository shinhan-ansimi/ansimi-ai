# 안심이 — AI 파트 (1.4 수집 + 2.1 정제·격자 생성 + 2.2 규칙 기반 스코어링)

간트차트 상 AI 담당 작업 중 **1.4 위험 데이터 조사·수집**, **2.1 정제·격자 생성**,
**2.2 v1 규칙 가중치 위험도**를 실제로 돌아가는 파이프라인으로 구현한 저장소입니다.
서울시 공공데이터(CCTV·보안등·비상벨·안심귀갓길 등)를 수집해 정제하고, 서울 전역을
100m×100m 격자로 나눠 격자별 안전시설 개수·위험요인을 집계한 뒤, 가중치 기반 공식으로
0~100 안전도 점수(`safety_score`)를 계산합니다. 다음 단계인 **2.3 스코어링 API**는
여기서 만든 `risk_grid.csv`(`safety_score` 포함)를 FastAPI로 서빙하면 됩니다.

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
| 심야 생활인구, 범죄율 | ❌ mock | 파일 다운로드 방식 — 파일 미확보 |

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
│   ├── pipeline.py              # collect → clean → grid 한번에 실행
│   └── output/                  # 실행 결과물 (git 미추적 — 로컬에서 재생성)
├── data_raw/                    # 다운받은 원본 SHP/CSV (git 미추적, 직접 받아서 채울 것)
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
```

`.env.example`에 채워야 할 키/파일 경로가 전부 정리돼 있습니다. 카테고리 하나가 비어있으면
그 카테고리만 mock으로 자동 대체되고 나머지는 정상 진행됩니다.

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

## 다음 단계(2.3)와의 연결

`risk_grid.csv`에 이미 `safety_score`(0~100)가 들어있으므로, 2.3에서는 FastAPI
`/score` 같은 엔드포인트로 이 파일(또는 이걸 옮긴 PostGIS 테이블)을 읽어 좌표나 격자
ID로 조회해 반환하면 됩니다.
