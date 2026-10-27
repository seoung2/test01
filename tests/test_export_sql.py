"""export_sql 테스트. 아래 표는 동작 확인용으로 만든 가짜 데이터다."""

import sqlite3
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_sql  # noqa: E402

DF = pd.DataFrame({
    "출처": ["시군구(소규모)", "시군구(소규모)"],
    "시설명": ["가나", "다'라"],
    "시도": ["경상북도", "전라남도"],
    "유효저수량": ["1.5", None],
    "준공연도": ["1961", None],
})


class ExportSqlTest(unittest.TestCase):
    def test_sqlite_script_runs_and_round_trips(self):
        db = sqlite3.connect(":memory:")
        db.executescript(export_sql.build_sql(DF, "sqlite"))
        rows = db.execute("SELECT name, sido, effective_storage, completed_year FROM reservoirs"
                          " ORDER BY id").fetchall()
        self.assertEqual(rows, [("가나", "경상북도", 1.5, 1961), ("다'라", "전라남도", None, None)])

    def test_mysql_escapes_backslash_and_sets_charset(self):
        sql = export_sql.build_sql(DF.assign(시설명=["a\\b", "c"]), "mysql")
        self.assertIn("SET NAMES utf8mb4;", sql)
        self.assertIn("'a\\\\b'", sql)
        self.assertIn("AUTO_INCREMENT", sql)

    def test_inserts_are_batched(self):
        big = pd.concat([DF] * 600, ignore_index=True)
        sql = export_sql.build_sql(big, "postgresql")
        self.assertEqual(sql.count("INSERT INTO"), 3)  # 1200행 / 500


if __name__ == "__main__":
    unittest.main()
