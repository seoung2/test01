"""build_reservoir_list 테스트. 아래 표는 동작 확인용으로 만든 가짜 데이터다."""

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

try:
    import xlwt
except ImportError:
    xlwt = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_reservoir_list as brl  # noqa: E402

KRC = pd.DataFrame({
    "표준시설코드": ["A001", "A002"],
    "시설명": ["가나저수지", "다라저수지"],
    "소재지": ["경기 가상시 가나동 1", "전남 가상군 다라면 2"],
    "총저수량(천㎥)": ["1,234.5", "200"],
    "수혜면적(ha)": ["50", "10"],
})

STD = pd.DataFrame({
    "시설명": ["가나 저수지", "마바저수지"],
    "시도명": ["경기도", "충청북도"],
    "시군구명": ["가상시", "가상군"],
    "총저수량(㎥)": ["999000", "50000"],
    "수혜면적(㎢)": ["0.3", "0.1"],
    "관리기관명": ["가상시청", "가상군청"],
})


class BuildReservoirListTest(unittest.TestCase):
    def test_normalize_header_splits_unit(self):
        self.assertEqual(brl.normalize_header("총저수량 (천㎥)"), ("총저수량", "천㎥"))

    def test_units_are_converted(self):
        std = brl.standardize(STD, "지방자치단체")
        self.assertAlmostEqual(std["총저수량"].iloc[0], 999.0)
        self.assertAlmostEqual(std["수혜면적"].iloc[0], 30.0)

    def test_sido_parsed_from_address(self):
        krc = brl.standardize(KRC, "한국농어촌공사")
        self.assertEqual(list(krc["시도"]), ["경기도", "전라남도"])
        self.assertEqual(list(krc["시군구"]), ["가상시", "가상군"])
        self.assertAlmostEqual(krc["총저수량"].iloc[0], 1234.5)

    def test_merge_prefers_krc_and_dedups(self):
        merged = brl.merge_sources([brl.standardize(KRC, "한국농어촌공사"),
                                    brl.standardize(STD, "지방자치단체")])
        self.assertEqual(len(merged), 3)
        gana = merged[merged["시설코드"] == "A001"]
        self.assertEqual(gana["출처"].iloc[0], "한국농어촌공사")

    def test_merge_keeps_same_name_within_one_source(self):
        same = pd.concat([KRC.iloc[[0]], KRC.iloc[[0]].assign(표준시설코드="A009")])
        merged = brl.merge_sources([brl.standardize(same, "한국농어촌공사")])
        self.assertEqual(len(merged), 2)

    @unittest.skipUnless(xlwt, "xlwt 가 없으면 .xls 테스트 파일을 만들 수 없음")
    def test_small_reservoir_xls(self):
        rows = [
            ["전국 시군구 관리 소규모 저수지 현황"],
            ["관리번호", "시설명", "위치", "", "", "", "설치년도"],
            ["", "", "시도", "시군구", "읍면", "동리", "착공", "준공"],
            [],
            ["가상", 3],  # 시도 소계 행
            [1, "가나", "경북", "가상", "가면", "가리", 1960, 1961, 10, 2, "", 1.5, 0.4, 90, 3, 50],
            [2, "가나", '"', "〃", '"', "나리", "", 1945, 5, 1, "", 0.5, 0.2],
            [3, "다라", "포항시", "북구", "다면", "다리", "", "", 7, 1, "", 0.7],
            ["소계", 3],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.xls"
            book = xlwt.Workbook()
            sheet = book.add_sheet("최종")
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    sheet.write(r, c, value)
            book.save(str(path))
            df = brl.read_small_reservoir_xls(path)
        self.assertEqual(list(df["시설명"]), ["가나", "가나", "다라"])
        self.assertEqual(list(df["시도"]), ["경상북도"] * 3)
        self.assertEqual(list(df["시군구"]), ["가상", "가상", "포항시 북구"])
        self.assertEqual(df["지번주소"].iloc[1], "경상북도 가상 가면 나리")
        self.assertEqual(df["유효저수량"].iloc[0], 1.5)
        self.assertEqual(df["준공연도"].iloc[0], "1961")
        self.assertTrue(pd.isna(df["준공연도"].iloc[2]))

    def test_main_writes_outputs_from_cp949_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            KRC.to_csv(tmp / "krc.csv", index=False, encoding="cp949")
            STD.to_excel(tmp / "std.xlsx", index=False)
            brl.main(["--krc", str(tmp / "krc.csv"), "--std", str(tmp / "std.xlsx"),
                      "--out-dir", str(tmp / "out")])
            out = pd.read_csv(tmp / "out" / "reservoirs.csv", encoding="utf-8-sig")
            self.assertEqual(len(out), 3)
            summary = pd.read_excel(tmp / "out" / "reservoirs.xlsx", sheet_name="시도별요약")
            self.assertEqual(summary["합계"].sum(), 3)


if __name__ == "__main__":
    unittest.main()
