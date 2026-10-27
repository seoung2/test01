"""export_web_data 테스트. 아래 표는 동작 확인용으로 만든 가짜 데이터다."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_web_data as ewd  # noqa: E402


class ExportWebDataTest(unittest.TestCase):
    def test_export_compacts_rows_and_drops_empty_columns(self):
        df = pd.DataFrame({
            "출처": ["시군구(소규모)", "시군구(소규모)"],
            "시설명": ["가나", "다라"],
            "시도": ["경상북도", "전라남도"],
            "총저수량": [None, None],
            "유효저수량": [1.5, 20.0],
            "준공연도": ["1961", None],
        })
        with tempfile.TemporaryDirectory() as tmp:
            csv_path, out = Path(tmp) / "r.csv", Path(tmp) / "web" / "r.json"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            self.assertEqual(ewd.export(csv_path, out), 2)
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["columns"], ["시설명", "시도", "유효저수량", "준공연도", "출처"])
        self.assertEqual(payload["rows"][0], ["가나", "경상북도", 1.5, "1961", "시군구(소규모)"])
        self.assertEqual(payload["rows"][1][2:4], [20, None])


if __name__ == "__main__":
    unittest.main()
