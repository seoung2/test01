"""저수지 목록(CSV)을 홈페이지 위젯용 JSON 으로 변환한다.

용량을 줄이려고 {"columns": [...], "rows": [[...], ...]} 형태로 저장하고,
홈페이지에 보여줄 컬럼만 남긴다.

사용법:
    python scripts/export_web_data.py --csv data/reservoirs.csv --out web/data/reservoirs.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

WEB_COLUMNS = ["시설명", "시도", "시군구", "지번주소", "관리기관", "총저수량", "유효저수량",
               "수혜면적", "만수면적", "제당높이", "제당길이", "준공연도", "출처", "시설코드"]
NUMBER_COLUMNS = {"총저수량", "유효저수량", "수혜면적", "만수면적", "제당높이", "제당길이"}


def clean(value: object, numeric: bool) -> object:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if numeric:
        number = float(value)
        return int(number) if number.is_integer() else round(number, 4)
    return str(value).strip() or None


def export(csv_path: Path, out_path: Path) -> int:
    df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig")
    for col in NUMBER_COLUMNS & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # 원본에 아예 없는 컬럼(모든 값이 비어 있음)은 내보내지 않는다
    columns = [c for c in WEB_COLUMNS if c in df.columns and df[c].notna().any()]
    rows = [[clean(v, c in NUMBER_COLUMNS) for c, v in zip(columns, row)]
            for row in df[columns].itertuples(index=False)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"columns": columns, "rows": rows}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default=Path("data/reservoirs.csv"), type=Path)
    parser.add_argument("--out", default=Path("web/data/reservoirs.json"), type=Path)
    args = parser.parse_args(argv)
    count = export(args.csv, args.out)
    print(f"저수지 {count:,}개 -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
