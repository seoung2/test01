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

    def test_supabase_files_split_data_and_enable_rls(self):
        big = pd.concat([DF] * 2000, ignore_index=True)  # 4000행 -> 데이터 파일 2개
        files = export_sql.build_supabase_files(big)
        self.assertEqual(sorted(files), ["01_schema.sql", "02_data_1.sql", "02_data_2.sql", "all.sql"])
        schema = files["01_schema.sql"]
        self.assertIn("GENERATED ALWAYS AS IDENTITY", schema)
        self.assertIn("ENABLE ROW LEVEL SECURITY", schema)
        self.assertIn("FOR SELECT TO anon, authenticated USING (true)", schema)
        self.assertLess(schema.index("DROP VIEW"), schema.index("DROP TABLE"))
        self.assertNotIn("CREATE VIEW", schema)  # 테이블 하나만 만든다
        self.assertEqual(files["02_data_1.sql"].count("INSERT INTO"), 6)  # 3000행 / 500
        self.assertEqual(files["02_data_2.sql"].count("INSERT INTO"), 2)
        self.assertEqual(files["all.sql"], "".join(files[k] for k in sorted(files) if k != "all.sql"))

    def test_supabase_csv_uses_db_column_names(self):
        csv = export_sql.supabase_csv(DF)
        self.assertEqual(list(csv.columns), [col for col, *_ in export_sql.COLUMNS])
        self.assertEqual(csv["name"].tolist(), ["가나", "다'라"])


if __name__ == "__main__":
    unittest.main()
