"""Run the bounded marketplace regression suite with live HTTP and DB connections forbidden."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main() -> int:
    loader = unittest.TestLoader()
    with patch("psycopg.connect", side_effect=AssertionError("Live DB access forbidden in regression tests")), \
         patch("requests.sessions.Session.request", side_effect=AssertionError("Live HTTP forbidden in regression tests")):
        suite = unittest.TestSuite()
        for module in ("test_rakuten_search_client", "test_rakuten_marketplace_evidence", "test_marketplace_staged_search", "test_marketplace_pack_counts",
                       "test_quasi_drug_compliance", "test_diagnose_rakuten_marketplace",
                       "test_listing_batch_fast_pipeline"):
            suite.addTests(loader.loadTestsFromName(module))
        import test_rakuten_listing_payload as fixtures
        case = fixtures.RakutenListingPhase1Tests
        for name in loader.getTestCaseNames(case):
            if "marketplace" in name or name.startswith("test_forced_listing"):
                suite.addTest(case(name))
        result = unittest.TextTestRunner(verbosity=1, buffer=True).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
