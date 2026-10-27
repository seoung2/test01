"""저수지 목록(CSV)을 데이터베이스에 넣는 SQL 스크립트로 변환한다.

테이블 생성(CREATE TABLE)과 데이터 입력(INSERT)이 한 파일에 들어 있어, 실행하면
reservoirs 테이블이 새로 만들어진다. 이미 있으면 지우고 다시 만든다.

사용법:
    python scripts/export_sql.py --dialect mysql      > sql/reservoirs_mysql.sql
    python scripts/export_sql.py --dialect postgresql --out sql/reservoirs_postgresql.sql
    python scripts/export_sql.py --dialect sqlite     --out sql/reservoirs_sqlite.sql

지원 DB: mysql(MySQL 5.7+/MariaDB 10.2+), postgresql(12+), sqlite(3)
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

TABLE = "reservoirs"
BATCH_SIZE = 500  # INSERT 한 문장에 넣을 행 수

# (DB 컬럼명, CSV 컬럼명, 타입, 설명). 타입은 세 DB 에서 모두 쓰는 표준 타입만 쓴다.
COLUMNS = [
    ("source", "출처", "VARCHAR(20)", "출처"),
    ("facility_code", "시설코드", "VARCHAR(30)", "시설코드(관리번호)"),
    ("name", "시설명", "VARCHAR(100) NOT NULL", "시설명"),
    ("sido", "시도", "VARCHAR(20)", "시도"),
    ("sigungu", "시군구", "VARCHAR(40)", "시군구"),
    ("address", "지번주소", "VARCHAR(255)", "지번주소"),
    ("road_address", "도로명주소", "VARCHAR(255)", "도로명주소"),
    ("manager", "관리기관", "VARCHAR(100)", "관리기관"),
    ("total_storage", "총저수량", "DECIMAL(14,4)", "총저수량(천㎥)"),
    ("effective_storage", "유효저수량", "DECIMAL(14,4)", "유효저수량(천㎥)"),
    ("benefit_area", "수혜면적", "DECIMAL(14,4)", "수혜면적(ha)"),
    ("basin_area", "유역면적", "DECIMAL(14,4)", "유역면적(ha)"),
    ("full_water_area", "만수면적", "DECIMAL(14,4)", "만수면적(ha)"),
    ("dam_height", "제당높이", "DECIMAL(10,2)", "제당높이(m)"),
    ("dam_length", "제당길이", "DECIMAL(10,2)", "제당길이(m)"),
    ("completed_year", "준공연도", "SMALLINT", "준공연도"),
    ("latitude", "위도", "DECIMAL(10,7)", "위도"),
    ("longitude", "경도", "DECIMAL(10,7)", "경도"),
    ("base_date", "데이터기준일자", "DATE", "데이터기준일자"),
]
TEXT_TYPES = ("VARCHAR", "DATE")

ID_COLUMN = {
    "mysql": "id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY",
    "postgresql": "id SERIAL PRIMARY KEY",
    "sqlite": "id INTEGER PRIMARY KEY AUTOINCREMENT",
}
INDEXES = [("idx_reservoirs_region", "sido, sigungu"), ("idx_reservoirs_name", "name")]


def quote(value: str, dialect: str) -> str:
    value = value.replace("'", "''")
    if dialect == "mysql":  # MySQL 은 기본 설정에서 \ 를 이스케이프 문자로 본다
        value = value.replace("\\", "\\\\")
    return f"'{value}'"


def literal(value: object, sql_type: str, dialect: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)) or value == "":
        return "NULL"
    if sql_type.startswith(TEXT_TYPES):
        return quote(str(value).strip(), dialect)
    number = float(value)
    if sql_type == "SMALLINT":
        return str(int(number))
    return repr(int(number)) if number.is_integer() else repr(number)


def create_table(dialect: str) -> list[str]:
    lines = [f"  {ID_COLUMN[dialect]}"]
    for col, _, sql_type, comment in COLUMNS:
        extra = f" COMMENT {quote(comment, dialect)}" if dialect == "mysql" else ""
        lines.append(f"  {col} {sql_type}{extra}")
    options = (" ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
               f" COMMENT={quote('전국 저수지 목록', dialect)}" if dialect == "mysql" else "")
    sql = [f"DROP TABLE IF EXISTS {TABLE};",
           f"CREATE TABLE {TABLE} (\n" + ",\n".join(lines) + f"\n){options};"]
    if dialect == "postgresql":
        sql.append(f"COMMENT ON TABLE {TABLE} IS {quote('전국 저수지 목록', dialect)};")
        sql += [f"COMMENT ON COLUMN {TABLE}.{col} IS {quote(comment, dialect)};"
                for col, _, _, comment in COLUMNS]
    sql += [f"CREATE INDEX {name} ON {TABLE} ({cols});" for name, cols in INDEXES]
    return sql


def build_sql(df: pd.DataFrame, dialect: str) -> str:
    header = [
        "-- 전국 저수지 목록 (scripts/export_sql.py 로 생성)",
        f"-- DB: {dialect}, 행 수: {len(df):,}",
        f"-- 실행하면 {TABLE} 테이블을 지우고 새로 만듭니다.",
    ]
    if dialect == "mysql":
        header.append("SET NAMES utf8mb4;")
    sql = header + create_table(dialect)
    sql.append("START TRANSACTION;" if dialect == "mysql" else "BEGIN;")

    names = ", ".join(col for col, *_ in COLUMNS)
    records = df.reindex(columns=[csv_col for _, csv_col, _, _ in COLUMNS]).itertuples(index=False)
    values = ["(" + ", ".join(literal(v, t, dialect) for v, (_, _, t, _) in zip(row, COLUMNS)) + ")"
              for row in records]
    for start in range(0, len(values), BATCH_SIZE):
        chunk = ",\n".join(values[start:start + BATCH_SIZE])
        sql.append(f"INSERT INTO {TABLE} ({names}) VALUES\n{chunk};")
    sql.append("COMMIT;")
    return "\n".join(sql) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default=Path("data/reservoirs.csv"), type=Path)
    parser.add_argument("--dialect", choices=sorted(ID_COLUMN), default="mysql")
    parser.add_argument("--out", type=Path, help="저장할 파일 (생략하면 화면에 출력)")
    args = parser.parse_args(argv)

    df = pd.read_csv(args.csv, dtype=str, encoding="utf-8-sig")
    sql = build_sql(df, args.dialect)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(sql, encoding="utf-8")
        print(f"저수지 {len(df):,}개 -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    sys.exit(main())
