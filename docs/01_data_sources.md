# 1.4 위험 데이터 조사·수집 — 데이터 소스 정리

안심이(AI 안심귀갓길) 서비스의 "경로 안전도 스코어링" 입력값으로 쓸 공공 데이터를 조사한 결과입니다.
전부 **서울 열린데이터광장(data.seoul.go.kr)** 또는 **공공데이터포털(data.go.kr)** 에서 제공하는 공식 데이터이며,
대부분 Open API(실시간 호출) + 파일 다운로드(CSV/XLSX) 두 가지 방식을 같이 제공합니다.

## 선정한 데이터셋

| 구분 | 데이터셋명 | 제공처 | 공간단위 | 접근방식 | 인증키 | 활용(격자 feature) |
|---|---|---|---|---|---|---|
| 안전시설(+) | 안전비상벨(안심벨) 설치 위치 | 서울 열린데이터광장 [OA-15253](https://data.seoul.go.kr/dataList/OA-15253/F/1/datasetView.do) / [data.go.kr](https://www.data.go.kr/data/15075539/fileData.do) | 위경도 포인트 | OpenAPI + 파일 | 필요(무료 발급) | 격자 내 비상벨 개수, 최단거리 |
| 안전시설(+) | CCTV(방범용) 설치 현황 | 서울 열린데이터광장 Open API [OA-](https://data.seoul.go.kr/) (자치구별 제공) | 위경도 포인트 | OpenAPI + 파일 | 필요 | 격자 내 CCTV 대수, 최단거리 |
| 안전시설(+) | 보안등 설치 위치 | 서울 열린데이터광장(자치구별) | 위경도 포인트 | OpenAPI + 파일 | 필요 | 격자 내 보안등 밀도(야간 조도 proxy) |
| 안전시설(+) | 경찰관서(지구대·파출소) 위치 | 서울 열린데이터광장 / 경찰청 | 위경도 포인트 | 파일 | 불필요~필요 | 최단거리(출동 반경 proxy) |
| 안전시설(+) | 24시 편의점 위치 | 소상공인시장진흥공단 상가(상권)정보 [data.go.kr 15083033](https://www.data.go.kr/data/15083033/openapi.do) | 위경도 포인트 | OpenAPI | 필요 | 격자 내 야간 영업시설 개수 |
| 위험요인(−) | 행정동 단위 서울 생활인구(내국인, 심야 0~5시) | 서울 열린데이터광장 [OA-14991](https://data.seoul.go.kr/dataList/OA-14991/S/1/datasetView.do) (집계구 단위는 [OA-14979](https://data.seoul.go.kr/dataList/OA-14979/S/1/datasetView.do)) | 행정동/집계구 | 파일(시간대별 대용량) | 필요 | 심야 유동인구 적은 구역 가중치↑(인적 드문 골목) |
| 위험요인(−) | 서울시 5대범죄 발생현황 통계(자치구별) | 서울 열린데이터광장 [316](https://data.seoul.go.kr/dataList/316/S/2/datasetView.do), 발생장소별 [10943](https://data.seoul.go.kr/dataList/10943/S/2/datasetView.do) / 경찰청 [data.go.kr 15054738](https://www.data.go.kr/data/15054738/fileData.do) | 자치구 | 파일(연간 집계) | 불필요 | 자치구 기준 범죄발생률 가중치(격자에 구 단위로 배분) |
| 경로(ground truth) | **안심귀갓길 경로** (서울시 공식 지정 362개 구간) | 서울 열린데이터광장 [OA-21695](https://data.seoul.go.kr/dataList/OA-21695/S/1/datasetView.do) / [data.go.kr](https://www.data.go.kr/data/15112099/fileData.do) | 라인(경로/링크) | SHP/XLSX 다운로드 | 필요 | `on_safe_route`(공식 안전경로 통과 여부), `dist_to_safe_route_m` — 2.2 점수 검증용 ground truth로도 활용 |
| 안전시설(+) | **안심귀갓길 안전시설물** (CCTV·안심벨·안내표지판, 경로ID 연계) | 서울 열린데이터광장 [OA-21696](https://data.seoul.go.kr/dataList/OA-21696/S/1/datasetView.do) / [data.go.kr](https://www.data.go.kr/data/15112100/fileData.do) | 위경도 포인트 | OpenAPI/파일 | 필요 | `route_cctv_count`, `route_emergency_bell_count`, `route_signage_count` |
| 안전시설(+) | **안심귀갓길 서비스** (안심택배함, 안심귀가길 지킴이집) | 서울 열린데이터광장 [OA-21697](https://data.seoul.go.kr/dataList/OA-21697/S/1/datasetView.do) | 위경도 포인트 | OpenAPI/파일 | 필요 | `safe_delivery_box_count`, `safe_route_guardian_house_count` |

> 참고: 서울 열린데이터광장 Open API 입출력 인자(공통) — [data.go.kr 15125824](https://www.data.go.kr/data/15125824/openapi.do?recommendDataYn=Y)

### ⚠️ 전체 CCTV 좌표 통합 API는 현재 없음 (2026 기준)

서울시 전체 CCTV를 명칭·주소·좌표까지 한 번에 주는 통합 API(**"서울시 안심이 CCTV 연계 현황"**, [OA-20923](https://data.seoul.go.kr/dataList/OA-20923/S/1/datasetView.do))가 있었지만, **2026.02.10 서비스 종료**됐습니다. 종료 사유가 "안심주소에 IP 노출로 국정원 지적"이라고 명시돼 있어서, 보안상의 이유로 CCTV 정확 좌표 공개 자체가 전반적으로 축소되는 추세입니다. 그래서:

- CCTV는 자치구별로 흩어진 개별 데이터셋(종로구/강북구/금천구/동작구/강서구 등, 구마다 공개 여부가 다름)에 의존해야 하고, 커버리지가 들쭉날쭉합니다.
- 위 표의 **"안심귀갓길 안전시설물"(OA-21696)** 은 국정원 지적을 받은 통합현황 API와는 별개 사업(안심귀갓길 조성사업)이라 CCTV 좌표가 살아있고, 이게 현재로선 가장 안정적인 CCTV 보조 소스입니다.
- `collectors/cctv.py`(자치구별) 의존도를 낮추고, `collectors/route_facilities.py`(안심귀갓길 연계)를 메인으로, 자치구별 CCTV는 보조로 두는 구조를 권장합니다.

## API 호출 패턴

서울 열린데이터광장 Open API는 모든 서비스가 동일한 URL 규칙을 씁니다.

```
http://openapi.seoul.go.kr:8088/{인증키}/{응답형식:json|xml}/{서비스명}/{요청시작행}/{요청종료행}/
```

- 인증키: [data.seoul.go.kr](https://data.seoul.go.kr) 회원가입 후 즉시 무료 발급(일 1,000회 제한, 증빙 시 상향 가능)
- 한 번에 최대 1,000행까지 조회 가능 → 전체 수집 시 페이지네이션 필요(1~1000, 1001~2000 …)
- 서비스명은 데이터셋마다 다름(예: CCTV·보안등·비상벨은 자치구별로 서비스명이 갈리는 경우가 많아, 수집기에서 자치구 리스트를 순회하도록 구현)

공공데이터포털(data.go.kr) 쪽은 `serviceKey`, `pageNo`, `numOfRows` 쿼리 파라미터 방식(REST)이 기본입니다.

## 인증키는 서비스별로 따로 발급됨

서울 열린데이터광장은 계정 하나에 공용키 하나가 아니라, **"Open API 서비스 신청"을 할 때마다 그 서비스 전용 키**를 발급합니다. 이 프로젝트에서 신청할 만한 서비스가 CCTV·보안등·비상벨·생활인구·범죄·안심귀갓길 경로·안전시설물·서비스 — 총 8개라서, 키도 8개가 생기는 게 정상입니다. `config.py`의 `SEOUL_KEY_ENV_MAP`에 카테고리별 `.env` 변수명을 매핑해뒀고(`SEOUL_KEY_CCTV`, `SEOUL_KEY_SAFE_ROUTE` 등), `get_seoul_key(category)`가 해당 카테고리 전용 키를 찾아 쓰도록 구현했습니다. 어떤 카테고리에 키가 없으면 공용 폴백키(`SEOUL_OPENAPI_KEY`)를 시도하고, 그마저 없으면 해당 카테고리만 mock으로 대체됩니다(전체 파이프라인이 죽지 않음).

## 좌표계 주의사항

- 서울 열린데이터광장 대부분 데이터는 **WGS84(위도/경도, EPSG:4326)** 로 제공되지만, 일부 구 단위 원본 파일은 **EPSG:5181(Korea 2000 / Central Belt)** 또는 **EPSG:2097** 로 내려오는 경우가 있음 → 수집 후 반드시 좌표계 확인 후 `pyproj`로 EPSG:4326 변환 필요(코드에 반영함).

## 이 샌드박스 환경의 제약

이 작업 환경은 보안상 `data.go.kr` / `data.seoul.go.kr` 로 나가는 외부 네트워크 호출이 허용돼 있지 않습니다(사내 egress 정책). 그래서:

1. 아래 수집기(`collectors/`) 코드는 **실제 운영 환경(FastAPI AI 서버, 본인 PC 등)에서 바로 쓸 수 있는 완성 코드**로 작성했습니다. 서비스키만 `.env`에 넣으면 그대로 동작합니다.
2. 이 세션 안에서 전체 파이프라인이 실제로 도는 것을 보여주기 위해, 각 수집기는 `USE_MOCK=1`일 때 **지리적으로 그럴듯한 샘플 데이터**를 생성하는 모드를 내장했습니다(실데이터 분포를 흉내낸 것일 뿐, 실제 좌표 아님 — 운영 전 반드시 실데이터로 교체).
