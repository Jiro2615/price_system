"""Focused category and listing regressions; real DB/HTTP is always forbidden."""
from contextlib import ExitStack, redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    with ExitStack() as stack:
        for target in ('psycopg.connect', 'requests.sessions.Session.request', 'urllib.request.OpenerDirector.open'):
            stack.enter_context(patch(target, side_effect=AssertionError('Live DB/HTTP forbidden')))
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            'tests.test_amazon_category_policy', 'tests.test_listing_precheck_order',
            'tests.test_listing_batch_local_data', 'tests.test_listing_batch_fast_pipeline',
            'tests.test_listing_execute_mock_e2e', 'tests.test_advertiser_encoding',
        ])
        output = io.StringIO()
        with redirect_stdout(output):
            result = unittest.TextTestRunner(verbosity=1).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
