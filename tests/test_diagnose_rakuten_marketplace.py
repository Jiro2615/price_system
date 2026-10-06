"""Mock-only diagnostic checks; no real HTTP or dotenv file access."""
import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import quote

from scripts import diagnose_rakuten_marketplace as diagnostic


APP = "fake-app-id-12345"
KEY = "fake-access-key-for-tests-123456789"


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "RAKUTEN_WEB_SERVICE_APPLICATION_ID": APP,
            "RAKUTEN_WEB_SERVICE_ACCESS_KEY": KEY,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch.object(diagnostic, "load_dotenv")
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)
        self.request = patch.object(diagnostic.requests, "get")
        self.get = self.request.start()
        self.addCleanup(self.request.stop)

    def response(self, status, body):
        self.get.return_value = Mock(status_code=status, ok=200 <= status < 300,
                                     json=Mock(return_value=body))

    def test_success_reads_once_without_outputting_product_data_or_keys(self):
        self.response(200, {"count": 30, "items": [{"itemName": KEY}]})
        records = diagnostic.diagnose()
        self.get.assert_called_once()
        self.assertEqual(self.get.call_args.kwargs["headers"], {"accessKey": KEY})
        self.assertFalse(self.get.call_args.kwargs["allow_redirects"])
        self.assertEqual(records[-1], {"stage": "response", "status": 200,
                                       "search_count": 30, "returned_items": 1})
        self.assertNotIn(KEY, json.dumps(records))

    def test_error_response_redacts_credentials_and_urls(self):
        for status in (400, 401, 403, 429, 503):
            with self.subTest(status=status):
                self.response(status, {"error": "denied", "error_description":
                                      f"bad key {KEY} app {APP} https://example.com/?key={KEY}"})
                records = diagnostic.diagnose()
                output = json.dumps(records)
                self.assertEqual(records[-1]["status"], status)
                self.assertEqual(records[-1]["error"], "denied")
                self.assertNotIn(KEY, output)
                self.assertNotIn(APP, output)
                self.assertNotIn("https://", output)

    def test_timeout_does_not_print_exception_url(self):
        self.get.side_effect = diagnostic.requests.Timeout(f"url?applicationId={APP}&accessKey={KEY}")
        result = diagnostic.diagnose()
        self.assertEqual(result[-1], {"stage": "transport_error", "exception_type": "Timeout"})

    def test_missing_key_makes_no_request(self):
        with patch.dict(os.environ, {"RAKUTEN_WEB_SERVICE_ACCESS_KEY": ""}):
            result = diagnostic.diagnose()
        self.get.assert_not_called()
        self.assertEqual(result[-1]["error"], "credentials_missing")

    def test_non_json_response_does_not_print_raw_body(self):
        self.response(403, {})
        self.get.return_value.json.side_effect = ValueError(KEY)
        self.assertEqual(diagnostic.diagnose()[-1]["error"], "non_json_response")

    def test_encoded_credentials_are_redacted(self):
        secret = "fake+special/secret="
        self.assertNotIn(quote(secret, safe=""), diagnostic.redact(quote(secret, safe=""), (secret,)))


if __name__ == "__main__":
    unittest.main()
