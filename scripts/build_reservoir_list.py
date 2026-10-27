"""전국 농업용 저수지 목록 생성 스크립트.

공공데이터포털에서 내려받은 두 종류의 원본 파일을 하나의 목록으로 합친다.

  * 한국농어촌공사_농업기반시설 시설제원_저수지 (농어촌공사 관리, 약 3,400개)
    https://www.data.go.kr/data/15044339/fileData.do
  * 전국저수지및댐표준데이터 (지방자치단체 관리)
    https://www.data.go.kr/data/15139218/standard.do

  * 전국 시군구 관리 소규모 저수지 현황 (행정안전부 계열 엑셀, 2007년경 작성)
    3단 병합 헤더 + 시도/시군구 소계 행이 섞인 .xls 양식

원본 파일은 기관·시점마다 컬럼명과 단위 표기가 조금씩 달라서, 컬럼은 동의어 목록으로
찾고 단위는 헤더의 괄호 표기(예: "총저수량(천㎥)")를 읽어 천㎥ / ha 로 맞춘다.

사용법:
    python scripts/build_reservoir_list.py \
        --krc data/raw/krc_*.csv --std data/raw/std_*.csv \
        --small data/raw/소규모저수지현황.xls --out-dir data
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# 출력 컬럼 -> 원본에서 찾을 컬럼명 후보 (앞에 있을수록 우선)
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "시설코드": ["표준시설코드", "시설코드", "저수지코드", "시설물코드"],
    "시설명": ["시설명", "저수지명", "시설물명", "저수지및댐명"],
    "시도": ["시도명", "시도"],
    "시군구": ["시군구명", "시군구"],
    "지번주소": ["소재지지번주소", "지번주소", "소재지주소", "소재지", "위치"],
    "도로명주소": ["소재지도로명주소", "도로명주소"],
    "관리기관": ["관리기관명", "관리기관", "관리주체", "시설관리자", "관리자"],
    "총저수량": ["총저수량"],
    "유효저수량": ["유효저수량"],
    "수혜면적": ["수혜면적", "몽리면적"],
    "유역면적": ["유역면적"],
    "만수면적": ["만수면적"],
    "제당높이": ["제당높이"],
    "제당길이": ["제당길이"],
    "준공연도": ["준공연도", "준공년도", "축조연도", "축조년도"],
    "위도": ["위도"],
    "경도": ["경도"],
    "데이터기준일자": ["데이터기준일자", "기준일자"],
}

OUTPUT_COLUMNS = ["출처", *COLUMN_SYNONYMS]

VOLUME_COLUMNS = ["총저수량", "유효저수량"]  # 천㎥ 로 통일
AREA_COLUMNS = ["수혜면적", "유역면적", "만수면적"]  # ha 로 통일

# 단위 표기 -> 목표 단위로의 배율
VOLUME_FACTORS = {"천㎥": 1, "천m3": 1, "천톤": 1, "만㎥": 10, "만m3": 10,
                  "만톤": 10, "백만㎥": 1000, "백만m3": 1000, "㎥": 0.001,
                  "m3": 0.001, "톤": 0.001}
AREA_FACTORS = {"ha": 1, "㎢": 100, "km2": 100, "㎡": 0.0001, "m2": 0.0001}

SIDO_ALIASES = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
    "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
    "울산": "울산광역시", "세종": "세종특별자치시", "세종시": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "강원도": "강원특별자치도",
    "충북": "충청북도", "충남": "충청남도", "전북": "전북특별자치도",
    "전라북도": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
    "경남": "경상남도", "제주": "제주특별자치도", "제주도": "제주특별자치도",
    "울산시": "울산광역시", "충남도": "충청남도", "충북도": "충청북도",
}
# 시도 칸에 시 이름이 들어간 경우: 시 -> (시도, 시군구 앞에 붙일 이름)
CITY_IN_SIDO = {
    "포항": ("경상북도", "포항시"), "포항시": ("경상북도", "포항시"),
    "전주": ("전북특별자치도", "전주시"), "전주시": ("전북특별자치도", "전주시"),
}
DITTO_CHARS = "\"'〃 "  # 이 문자만 있거나 빈칸이면 윗행과 같다는 뜻
SIDO_SUFFIXES = ("특별시", "광역시", "특별자치시", "특별자치도", "통합특별시", "도")


def normalize_header(header: str) -> tuple[str, str]:
    """'총저수량 (천㎥)' -> ('총저수량', '천㎥')"""
    text = re.sub(r"\s+", "", str(header))
    unit = ""
    match = re.search(r"[(\[]([^)\]]*)[)\]]", text)
    if match:
        unit = match.group(1)
        text = text[: match.start()] + text[match.end():]
    return text, unit.replace("m³", "m3").replace("M3", "m3")


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없습니다: {path}")


def to_number(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(",", "").str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_sido(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    value = re.sub(r"\s+", "", value)
    return SIDO_ALIASES.get(value, value)


def split_address(address: object) -> tuple[str, str]:
    """주소 앞부분에서 (시도, 시군구) 를 뽑는다."""
    if not isinstance(address, str):
        return "", ""
    tokens = address.split()
    if not tokens:
        return "", ""
    sido = normalize_sido(tokens[0])
    if sido not in SIDO_ALIASES.values() and not sido.endswith(SIDO_SUFFIXES):
        return "", ""
    sigungu = []
    for token in tokens[1:3]:
        if token.endswith(("시", "군", "구")):
            sigungu.append(token)
        else:
            break
    return sido, " ".join(sigungu)


def standardize(raw: pd.DataFrame, source: str) -> pd.DataFrame:
    headers = {col: normalize_header(col) for col in raw.columns}
    out = pd.DataFrame(index=raw.index)
    out["출처"] = source

    for target, candidates in COLUMN_SYNONYMS.items():
        found = next(
            (col for name in candidates
             for col, (norm, _) in headers.items() if norm == name),
            None,
        )
        if found is None:
            out[target] = pd.NA
            continue
        values = raw[found]
        unit = headers[found][1]
        if target in VOLUME_COLUMNS or target in AREA_COLUMNS:
            factors = VOLUME_FACTORS if target in VOLUME_COLUMNS else AREA_FACTORS
            values = to_number(values)
            if unit in factors:
                values = values * factors[unit]
            else:
                print(f"[경고] {source} '{found}' 단위를 알 수 없어 원본 값 그대로 둡니다.",
                      file=sys.stderr)
        elif target in ("위도", "경도"):
            values = to_number(values)
        else:
            values = values.astype("string").str.strip()
        out[target] = values

    # 시도/시군구 컬럼이 없거나 빈 행은 주소에서 채운다
    address = out["지번주소"].fillna(out["도로명주소"])
    parsed = address.apply(split_address)
    out["시도"] = out["시도"].apply(normalize_sido)
    out["시도"] = out["시도"].mask(out["시도"] == "", parsed.str[0])
    out["시군구"] = out["시군구"].fillna("")
    out["시군구"] = out["시군구"].mask(out["시군구"] == "", parsed.str[1])

    out = out[out["시설명"].notna() & (out["시설명"] != "")]
    return out[OUTPUT_COLUMNS]


def read_small_reservoir_xls(path: Path, source: str = "시군구(소규모)") -> pd.DataFrame:
    """'전국 시군구 관리 소규모 저수지 현황' 엑셀을 표준 컬럼으로 읽는다.

    헤더가 3행(2~4행)에 걸쳐 병합돼 있고, 시도·시군구 소계 행(시설명 칸에 개수)이
    중간중간 섞여 있으며, 시도·시군구 칸은 '"', '〃' 나 빈칸으로 윗행 반복을 표시한다.
    """
    import xlrd

    sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)

    def cell(row: int, col: int) -> object:
        c = sheet.cell(row, col)
        if c.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
            return None
        return c.value.strip() if isinstance(c.value, str) else c.value

    def number(value: object) -> float | None:
        try:
            return float(str(value).replace(",", "")) if value not in (None, "") else None
        except ValueError:
            return None

    def text(value: object) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return "" if value is None else str(value).strip()

    records = []
    sido = sigungu = prev_name = prev_eupmyeon = prev_dongri = ""
    for row in range(4, sheet.nrows):
        name = cell(row, 1)
        if not isinstance(name, str) or not name:
            continue  # 소계(시설명 칸이 숫자)·빈 행
        # '가 재', '연  화2' 처럼 글자 사이에 넣은 공백을 없애고, '〃' 는 윗행 이름으로
        name = re.sub(r"\s+", "", name)
        if not name.strip(DITTO_CHARS):
            name = prev_name
        prev_name = name
        raw_sido, raw_sigungu = text(cell(row, 2)), text(cell(row, 3))
        if raw_sido.strip(DITTO_CHARS):
            sido = raw_sido
        if raw_sigungu.strip(DITTO_CHARS):
            sigungu = raw_sigungu
        if re.sub(r"\s+", "", sido) in CITY_IN_SIDO:
            row_sido, prefix = CITY_IN_SIDO[re.sub(r"\s+", "", sido)]
            row_sigungu = f"{prefix} {sigungu}".strip()
        else:
            row_sido, row_sigungu = normalize_sido(sido), sigungu
        # 읍면·동리는 빈칸이 정상일 수 있어(동 지역) 반복 기호가 있을 때만 윗행 값을 쓴다
        eupmyeon, dongri = text(cell(row, 4)), text(cell(row, 5))
        if eupmyeon and not eupmyeon.strip(DITTO_CHARS):
            eupmyeon = prev_eupmyeon
        if dongri and not dongri.strip(DITTO_CHARS):
            dongri = prev_dongri
        prev_eupmyeon, prev_dongri = eupmyeon, dongri
        year = number(cell(row, 7))
        records.append({
            "출처": source,
            "시설코드": text(cell(row, 0)),
            "시설명": name,
            "시도": row_sido,
            "시군구": row_sigungu,
            "지번주소": " ".join(t for t in (row_sido, row_sigungu, eupmyeon, dongri) if t),
            "관리기관": " ".join(t for t in (row_sido, row_sigungu) if t),
            "유효저수량": number(cell(row, 11)),  # 천톤 = 천㎥
            "수혜면적": number(cell(row, 9)),  # 몽리면적(ha)
            "유역면적": number(cell(row, 8)),
            "만수면적": number(cell(row, 12)),
            "제당높이": number(cell(row, 14)),
            "제당길이": number(cell(row, 15)),
            "준공연도": str(int(year)) if year else pd.NA,
        })
    df = pd.DataFrame.from_records(records).reindex(columns=OUTPUT_COLUMNS)
    return df.drop_duplicates()


def merge_sources(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """다른 출처에 이미 있는 저수지(시도·시군구·시설명 일치)는 앞 출처의 것만 남긴다.

    같은 출처 안에서는 이름이 같아도 서로 다른 저수지일 수 있어 그대로 둔다.
    """
    kept: list[pd.DataFrame] = []
    seen: set[str] = set()
    for frame in frames:
        key = (frame["시도"].fillna("") + "|" + frame["시군구"].fillna("") + "|"
               + frame["시설명"].str.replace(r"\s+", "", regex=True))
        kept.append(frame[~key.isin(seen)])
        seen.update(key)
    merged = pd.concat(kept, ignore_index=True)
    return merged.sort_values(["시도", "시군구", "시설명"], kind="stable").reset_index(drop=True)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby(["시도", "출처"]).size().unstack(fill_value=0)
            .assign(합계=lambda t: t.sum(axis=1)).reset_index())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--krc", nargs="*", default=[], type=Path,
                        help="한국농어촌공사 저수지 시설제원 파일 (CSV/XLSX)")
    parser.add_argument("--std", nargs="*", default=[], type=Path,
                        help="전국저수지및댐표준데이터 파일 (CSV/XLSX)")
    parser.add_argument("--small", nargs="*", default=[], type=Path,
                        help="전국 시군구 관리 소규모 저수지 현황 엑셀 (.xls)")
    parser.add_argument("--out-dir", default=Path("data"), type=Path)
    args = parser.parse_args(argv)

    frames = [standardize(read_table(p), "한국농어촌공사") for p in args.krc]
    frames += [standardize(read_table(p), "지방자치단체") for p in args.std]
    frames += [read_small_reservoir_xls(p) for p in args.small]
    if not frames:
        parser.error("--krc, --std, --small 로 원본 파일을 하나 이상 지정하세요.")

    result = merge_sources(frames)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "reservoirs.csv"
    xlsx_path = args.out_dir / "reservoirs.xlsx"
    result.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path) as writer:
        result.to_excel(writer, sheet_name="전체목록", index=False)
        summarize(result).to_excel(writer, sheet_name="시도별요약", index=False)

    print(f"저수지 {len(result):,}개 -> {csv_path}, {xlsx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
