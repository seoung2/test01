# test01 — 전국 농업용 저수지 목록

## 현재 목록: `data/reservoirs.csv`, `data/reservoirs.xlsx`

**전국 시군구 관리 소규모 저수지 현황**(`data/raw/small_reservoirs_sigungu.xls`, 2007년경 작성된 엑셀)으로 만든
**14,366개** 저수지 목록입니다.

| 시도 | 개수 | | 시도 | 개수 |
| --- | ---: | --- | --- | ---: |
| 경상북도 | 4,954 | | 강원특별자치도 | 260 |
| 경상남도 | 2,695 | | 대구광역시 | 190 |
| 전라남도 | 2,248 | | 부산광역시 | 120 |
| 전북특별자치도 | 1,891 | | 광주광역시 | 93 |
| 충청남도 | 737 | | 인천광역시 | 21 |
| 충청북도 | 548 | | 대전광역시 | 16 |
| 경기도 | 300 | | 제주특별자치도 | 1 |
| 울산광역시 | 292 | | | |

원본 사용 시 주의할 점:

- 원본 머리글의 합계는 14,328개입니다. 시도별 소계와 비교하면 강원(소계 221, 실제 행 260)과
  경북(소계 4,955, 실제 행 4,954)만 다르며, 목록에는 실제 행을 모두 담았습니다.
- 시군구 관리 **소규모** 저수지만 들어 있습니다. 한국농어촌공사 관리 저수지(약 3,400개)는
  아래 `--krc` 파일을 추가해야 합니다.
- 2007년 당시 행정구역 기준입니다(예: 연기군, 마산·진해, 북제주). 시도 이름만 현재 명칭으로 바꿨고,
  시군구 이름은 원본 표기(`강서`, `합천군` 처럼 접미사가 섞임)를 그대로 둡니다.
- 준공연도 `1945`는 원본에서 '해방 이전 축조'를 뜻하는 값으로 많이 쓰였습니다. 원본의 `#REF!` 오류 칸은 빈 값으로 둡니다.
- 관리기관은 원본에 별도 칸이 없어 해당 시도·시군구로 채웠습니다.
- 원본에서 단위를 다르게 입력한 것으로 보이는 값(유효저수량 0.05천㎥ 미만 75건, 제당높이 508m 등)은 그대로 두었습니다.

## 홈페이지에 적용하기

### 방법 1. 위젯 (DB 없이 파일만 올리기)

`web/` 폴더(`reservoir-list.js`, `data/reservoirs.json`)를 홈페이지 서버에 올리고,
표를 보여줄 페이지에 아래 두 줄을 넣습니다. 검색, 시도·시군구 필터, 열 정렬, 페이지 넘김,
CSV 내려받기가 되는 표가 나타납니다. 다른 라이브러리는 필요 없습니다.

```html
<div class="reservoir-list" data-src="/reservoirs/data/reservoirs.json"></div>
<script src="/reservoirs/reservoir-list.js" defer></script>
```

- `data-src`: JSON 경로. 생략하면 스크립트 옆의 `data/reservoirs.json`을 읽습니다.
- `data-page-size`: 한 페이지 행 수(기본 50). `data-sido`: 처음에 선택해 둘 시도(예: `경상북도`).
- 색은 홈페이지 CSS에서 `.reservoir-list { --rsv-accent: #0a7; }`처럼 바꿀 수 있습니다.
- 예시 페이지: `web/index.html` (`cd web && python -m http.server` 후 http://localhost:8000).
- 목록을 갱신했으면 `python scripts/export_web_data.py`로 JSON을 다시 만듭니다.

### 방법 2. 데이터베이스 (SQL 스크립트)

`sql/` 폴더에 DB별 실행 스크립트가 있습니다. 실행하면 `reservoirs` 테이블을 만들고(이미 있으면 지우고 새로 만듦)
14,366행을 넣습니다.

| 파일 | DB | 실행 예 |
| --- | --- | --- |
| `sql/reservoirs_mysql.sql` | MySQL 5.7+ / MariaDB 10.2+ | `mysql --default-character-set=utf8mb4 -u 사용자 -p DB이름 < sql/reservoirs_mysql.sql` |
| `sql/reservoirs_postgresql.sql` | PostgreSQL 12+ | `psql -d DB이름 -f sql/reservoirs_postgresql.sql` |
| `sql/reservoirs_sqlite.sql` | SQLite 3 | `sqlite3 reservoirs.db < sql/reservoirs_sqlite.sql` |

phpMyAdmin을 쓰는 호스팅(카페24, 가비아 등)은 **가져오기** 메뉴에서 `reservoirs_mysql.sql`(약 3MB)을 올리면 됩니다.
문자셋은 utf8mb4입니다.

테이블 구조 (단위: 저수량 천㎥, 면적 ha, 길이 m):

| 컬럼 | 뜻 | 컬럼 | 뜻 |
| --- | --- | --- | --- |
| `id` | 일련번호(PK) | `total_storage` | 총저수량 |
| `source` | 출처 | `effective_storage` | 유효저수량 |
| `facility_code` | 시설코드(관리번호) | `benefit_area` | 수혜면적 |
| `name` | 시설명 | `basin_area` | 유역면적 |
| `sido` | 시도 | `full_water_area` | 만수면적 |
| `sigungu` | 시군구 | `dam_height` / `dam_length` | 제당높이 / 제당길이 |
| `address` / `road_address` | 지번 / 도로명 주소 | `completed_year` | 준공연도 |
| `manager` | 관리기관 | `latitude` / `longitude` / `base_date` | 위도 / 경도 / 데이터기준일자 |

인덱스: `(sido, sigungu)`, `name`. 예: `SELECT name, sigungu, effective_storage FROM reservoirs WHERE sido = '경상북도' ORDER BY effective_storage DESC;`

목록을 갱신했으면 `python scripts/export_sql.py --dialect mysql --out sql/reservoirs_mysql.sql`로 다시 만듭니다.

## 원본 데이터

공공데이터포털의 원본 파일을 합쳐 전국 농업용 저수지 목록(CSV/엑셀)을 만듭니다.

| 원본 | 관리 주체 | 링크 |
| --- | --- | --- |
| 한국농어촌공사_농업기반시설 시설제원_저수지 | 한국농어촌공사 (약 3,400개) | https://www.data.go.kr/data/15044339/fileData.do |
| 전국저수지및댐표준데이터 | 지방자치단체 | https://www.data.go.kr/data/15139218/standard.do |
| 전국 시군구 관리 소규모 저수지 현황 (`--small`) | 시군구 | `data/raw/small_reservoirs_sigungu.xls` |

## 사용법

1. 위 두 페이지에서 CSV(또는 XLSX) 파일을 내려받아 `data/raw/`에 둡니다.
2. 실행합니다.

```bash
pip install -r requirements.txt
python scripts/build_reservoir_list.py \
    --krc data/raw/<농어촌공사 파일>.csv \
    --std data/raw/<표준데이터 파일>.csv \
    --small data/raw/small_reservoirs_sigungu.xls \
    --out-dir data
```

3. `data/reservoirs.csv`(엑셀에서 바로 열리는 UTF-8 BOM)와 `data/reservoirs.xlsx`(`전체목록`, `시도별요약` 시트)가 생성됩니다.

## 처리 내용

- **컬럼 맞추기**: 파일마다 다른 컬럼명(`시설명`/`저수지명`, `관리기관명`/`관리주체` 등)을 동의어로 찾아 통일합니다.
- **단위 통일**: 헤더 괄호의 단위를 읽어 저수량은 **천㎥**(천톤도 같은 값), 면적은 **ha**로 바꿉니다. 단위가 없으면 원본 값 그대로 두고 경고를 출력합니다.
- **시도·시군구**: 해당 컬럼이 없으면 주소 앞부분에서 뽑고, `경기`→`경기도`, `강원도`→`강원특별자치도`처럼 정식 명칭으로 바꿉니다.
- **중복 제거**: 다른 출처에 시도·시군구·시설명(공백 무시)이 같은 저수지가 이미 있으면 앞 출처(농어촌공사 → 표준데이터 → 소규모 현황 순)를 남깁니다. 같은 출처 안의 동명 저수지는 서로 다른 시설일 수 있어 그대로 둡니다.
- **소규모 저수지 엑셀**: 3단 병합 헤더와 시도/시군구 소계 행을 건너뛰고, `"`·`〃`·빈칸은 윗행 값으로 채우며, 시도 칸에 들어간 시 이름(`포항시`, `전주`)은 해당 도로 바꿉니다.
- CSV는 UTF-8/CP949 인코딩을 자동으로 판별합니다.

출력 컬럼: `출처, 시설코드, 시설명, 시도, 시군구, 지번주소, 도로명주소, 관리기관, 총저수량, 유효저수량, 수혜면적, 유역면적, 만수면적, 제당높이, 제당길이, 준공연도, 위도, 경도, 데이터기준일자`

## 테스트

```bash
python -m unittest discover -s tests
```
