from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from zhaopin_salary.cleaning import parse_experience_bucket
from zhaopin_salary.pipelines import build_dedup_key


class CleaningTests(unittest.TestCase):
    def test_experience_bucket_ranges(self) -> None:
        self.assertEqual(parse_experience_bucket("1-3年"), "0-3年")
        self.assertEqual(parse_experience_bucket("3-5年"), "3-5年")
        self.assertEqual(parse_experience_bucket("5年以上"), "5年以上")

    def test_experience_bucket_special(self) -> None:
        self.assertEqual(parse_experience_bucket("经验不限"), "0-3年")
        self.assertEqual(parse_experience_bucket("应届生"), "0-3年")
        self.assertEqual(parse_experience_bucket(None), "unknown")
        self.assertEqual(parse_experience_bucket(""), "unknown")

    def test_build_dedup_key(self) -> None:
        a = {
            "job_url": " https://example.com/job/123 ",
            "company_name": " Foo Inc ",
            "job_title": " Python 开发工程师 ",
        }
        b = {
            "job_url": "https://example.com/job/123",
            "company_name": "foo inc",
            "job_title": "python 开发工程师",
        }
        self.assertEqual(build_dedup_key(a), build_dedup_key(b))


if __name__ == "__main__":
    unittest.main()

