import unittest
from summarize import comparable, compare_cases
from probe_support import REPO, no_db, challenge


class ProbeTests(unittest.TestCase):
    def test_relative_repo(self):
        self.assertTrue((REPO / "scripts" / "price_check_one_asin_db.py").is_file())

    def test_db_forbidden(self):
        with self.assertRaises(RuntimeError):
            no_db()

    def test_challenge(self):
        self.assertTrue(challenge("https://www.amazon.co.jp/ap/signin", ""))
        self.assertTrue(challenge("", "ロボットではない"))
        self.assertFalse(challenge("https://www.amazon.co.jp/dp/B07QP2L8LC", "商品"))

    def test_empty_never_passes(self):
        self.assertFalse(compare_cases({}, {})["baseline_matches"])

    def test_error_never_passes(self):
        a = {"baseline": {"system_error": True}}
        self.assertFalse(compare_cases(a, a)["baseline_matches"])

    def test_countdown_only(self):
        a = "929円 9月15日（5 時間 40 分以内にご注文の場合）"
        b = "929円 9月15日（5 時間 39 分以内にご注文の場合）"
        self.assertEqual(comparable(a), comparable(b))
        self.assertNotEqual(comparable(a), comparable(b.replace("929", "930")))
        self.assertNotEqual(comparable(a), comparable(b.replace("15日", "16日")))

    def test_same_price_different_quantity_detected(self):
        a = {"baseline": {"amazon_price": 2792, "available_qty": 2}}
        b = {"baseline": {"amazon_price": 2792, "available_qty": 15}}
        result = compare_cases(a, b)
        self.assertFalse(result["baseline_matches"])
        self.assertEqual(result["baseline_differences"], ["available_qty"])


if __name__ == "__main__":
    unittest.main()
