"""Canonical checker tests: no browser, network, DB or live worker."""
import importlib.util
from contextlib import ExitStack
from pathlib import Path
import unittest
import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

SOURCE = Path(__file__).parents[1] / 'scripts/price_check_one_asin_db.py'
spec = importlib.util.spec_from_file_location('checker_safety_test', SOURCE)
checker = importlib.util.module_from_spec(spec)
fake_db = ModuleType('db_config')
fake_db.connect_db = Mock(side_effect=AssertionError('DB access forbidden in tests'))
with patch.dict(sys.modules, {'scripts.db_config': fake_db, 'db_config': fake_db}):
    spec.loader.exec_module(checker)


class HumanVerificationStockTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_challenge_preserves_stock(self):
        page = Mock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock(return_value=True)
        result = await checker.check_amazon_one('B0BLS9FNWH', page=page)
        self.assertTrue(result['human_verification_required'])
        self.assertTrue(result['skip_product_persistence'])
        self.assertTrue(result['amazon_confirmation_waiting'])
        self.assertFalse(result['business_ng'])
        self.assertIsNone(result['available_qty'])
        # save_to_db must return before importing/configuring any DB connection.
        checker.save_to_db(result)
        fake_db.connect_db.assert_not_called()
        page.locator.assert_not_called()

    async def test_challenge_during_aod_is_not_business_ng_or_zero_stock(self):
        page = Mock()
        page.url = 'https://www.amazon.co.jp/dp/B0BLS9FNWH'
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock(return_value=False)
        mocks = {
            'get_first_text': AsyncMock(return_value=''),
            'verify_product_identity': AsyncMock(return_value=True),
            'select_one_time_purchase': AsyncMock(return_value=False),
            'get_title': AsyncMock(return_value='fixture'),
            'capture_main_image': AsyncMock(return_value={}),
            'detect_unsupported_direct_purchase_ui': AsyncMock(return_value=''),
            'read_buybox_info': AsyncMock(return_value={'in_text': ''}),
            'read_lowest_amazon_fulfilled_offer': AsyncMock(side_effect=checker._safety.HumanVerificationRequired()),
        }
        with ExitStack() as stack:
            for name, value in mocks.items():
                stack.enter_context(patch.object(checker, name, value))
            result = await checker.check_amazon_one('B0BLS9FNWH', page=page)
        self.assertTrue(result['skip_product_persistence'])
        self.assertFalse(result['business_ng'])
        self.assertIsNone(result['available_qty'])
        mocks['read_lowest_amazon_fulfilled_offer'].assert_awaited_once()
        checker.save_to_db(result)


if __name__ == '__main__':
    unittest.main()
