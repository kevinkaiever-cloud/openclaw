from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zhaopin_salary.salary import parse_salary


class ParseSalaryTests(unittest.TestCase):
    def test_parse_k_range(self) -> None:
        parsed = parse_salary("8k-15k/月")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 8000)
        self.assertEqual(parsed.salary_max, 15000)
        self.assertEqual(parsed.salary_period, "monthly")
        self.assertEqual(parsed.salary_months, 12)

    def test_parse_yearly_wan_range(self) -> None:
        parsed = parse_salary("20-30万/年")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 16667)
        self.assertEqual(parsed.salary_max, 25000)
        self.assertEqual(parsed.salary_period, "yearly")

    def test_parse_with_13_months(self) -> None:
        parsed = parse_salary("15-20k·13薪")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 15000)
        self.assertEqual(parsed.salary_max, 20000)
        self.assertEqual(parsed.salary_months, 13)

    def test_parse_daily_salary(self) -> None:
        parsed = parse_salary("500-800元/天")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 10875)
        self.assertEqual(parsed.salary_max, 17400)
        self.assertEqual(parsed.salary_period, "daily")

    def test_parse_hourly_salary(self) -> None:
        parsed = parse_salary("50-80元/小时")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 8700)
        self.assertEqual(parsed.salary_max, 13920)
        self.assertEqual(parsed.salary_period, "hourly")

    def test_parse_negotiable_salary(self) -> None:
        parsed = parse_salary("面议")
        self.assertFalse(parsed.salary_parsed)
        self.assertIsNone(parsed.salary_min)
        self.assertIsNone(parsed.salary_max)

    def test_parse_single_salary(self) -> None:
        parsed = parse_salary("12k/月")
        self.assertTrue(parsed.salary_parsed)
        self.assertEqual(parsed.salary_min, 12000)
        self.assertEqual(parsed.salary_max, 12000)


if __name__ == "__main__":
    unittest.main()

