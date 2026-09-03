from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import calc_store_targets as targets  # noqa: E402


class RakutenTargetPriceFloorTests(unittest.TestCase):
    def test_price_below_configured_floor_is_raised(self) -> None:
        self.assertEqual((1000, True), targets.apply_rakuten_target_price_floor(990, 1000))

    def test_price_at_or_above_floor_is_unchanged(self) -> None:
        self.assertEqual((1000, False), targets.apply_rakuten_target_price_floor(1000, 1000))
        self.assertEqual((1230, False), targets.apply_rakuten_target_price_floor(1230, 1000))

    def test_missing_price_is_not_created(self) -> None:
        self.assertEqual((None, False), targets.apply_rakuten_target_price_floor(None, 1000))

    def test_missing_or_zero_setting_keeps_the_price_unrestricted(self) -> None:
        self.assertEqual((790, False), targets.apply_rakuten_target_price_floor(790, None))
        self.assertEqual((790, False), targets.apply_rakuten_target_price_floor(790, 0))


if __name__ == "__main__":
    unittest.main()
