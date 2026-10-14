"""Run the selected company-ledger regressions with all live access forbidden."""
from pathlib import Path
from contextlib import redirect_stdout
import io
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    guards = [patch(target, side_effect=AssertionError("Live DB/API access is forbidden in this regression"))
              for target in ("psycopg.connect", "requests.sessions.Session.request", "urllib.request.OpenerDirector.open")]
    for guard in guards:
        guard.start()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames([
            "tests.test_company_brand_ng", "tests.test_listing_precheck_order", "tests.test_listing_batch_local_data",
            "tests.test_listing_batch_fast_pipeline", "tests.test_forced_word_policy", "tests.test_forced_word_classification_db",
        ])
        output = io.StringIO()
        with redirect_stdout(output):
            result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            print(output.getvalue())
        return 0 if result.wasSuccessful() else 1
    finally:
        for guard in reversed(guards):
            guard.stop()


if __name__ == "__main__":
    raise SystemExit(main())
