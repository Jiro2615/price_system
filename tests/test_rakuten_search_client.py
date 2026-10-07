"""No external HTTP, IP lookup, dotenv reads, real sleeping, or DB writes."""
import contextlib
import io
import os
import unittest
from unittest.mock import Mock, patch

from scripts.listing import rakuten_search_client as client


class SearchClientTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {
            "RAKUTEN_WEB_SERVICE_APPLICATION_ID": "fake-app",
            "RAKUTEN_WEB_SERVICE_ACCESS_KEY": "fake-secret-key-for-client-tests",
        }))
        self.stack.enter_context(patch.object(client, "load_dotenv"))
        self.stack.enter_context(patch.object(client, "_wait_for_slot"))
        self.sleep = self.stack.enter_context(patch.object(client.time, "sleep"))
        self.get = self.stack.enter_context(patch.object(client.requests, "get"))
        self.ip = self.stack.enter_context(patch.object(client, "public_ipv4", return_value="203.0.113.7"))
        client._logged_errors.clear()

    def response(self, status, payload, headers=None):
        return Mock(status_code=status, json=Mock(return_value=payload), headers=headers or {})

    def test_upper_and_lower_case_collections_and_wrappers(self):
        for key, wrapper in (("items", None), ("Items", None), ("items", "item"), ("Items", "Item")):
            item = {"itemName": "商品", "itemPrice": 200}
            self.get.return_value = self.response(200, {key: [item if wrapper is None else {wrapper: item}]})
            self.assertEqual(client.search_items("商品"), [item])
        request = self.get.call_args.kwargs
        self.assertEqual(request["params"]["sort"], "standard")
        self.assertEqual(request["params"]["formatVersion"], 2)
        self.assertEqual(request["headers"], {"accessKey": "fake-secret-key-for-client-tests"})
        self.assertNotIn("Origin", request["headers"])
        self.assertFalse(request["allow_redirects"])

    def test_postage_filter_can_be_removed_without_removing_availability(self):
        self.get.return_value = self.response(200, {"items": []})
        client.search_items("商品", postage_included=False)
        params = self.get.call_args.kwargs["params"]
        self.assertNotIn("postageFlag", params)
        self.assertEqual(params["availability"], 1)
        self.assertEqual(params["hits"], 30)
        client.search_items("商品")
        self.assertEqual(self.get.call_args.kwargs["params"]["postageFlag"], 1)

    def test_ip_denial_is_logged_as_system_error_without_secrets(self):
        self.get.return_value = self.response(403, {"errors": {"errorCode": "403", "errorMessage": "CLIENT_IP_NOT_ALLOWED"}})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for _ in range(2):
                with self.assertRaises(client.RakutenSearchError) as caught:
                    client.search_items("商品")
                self.assertEqual(caught.exception.code, "CLIENT_IP_NOT_ALLOWED")
                self.assertIn("許可IP設定", str(caught.exception))
        self.assertEqual(output.getvalue().count("RAKUTEN_SEARCH_ERROR"), 1)
        self.ip.assert_called_once()
        self.assertIn('"product_ng": false', output.getvalue())
        self.assertNotIn("fake-app", output.getvalue())
        self.assertNotIn("fake-secret", output.getvalue())

    def test_error_message_echoing_keys_is_redacted(self):
        self.get.return_value = self.response(401, {"error": "invalid_key", "error_description":
                                                   "fake-app fake-secret-key-for-client-tests https://example.com/key"})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError) as caught:
            client.search_items("商品")
        self.assertNotIn("fake-app", str(caught.exception))
        self.assertNotIn("fake-secret", str(caught.exception))
        self.assertNotIn("https://", str(caught.exception))

    def test_empty_items_are_no_results_but_missing_items_is_error(self):
        self.get.return_value = self.response(200, {"Items": []})
        self.assertEqual(client.search_items("商品"), [])
        self.get.return_value = self.response(200, {})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")

    def test_documented_not_found_is_empty_but_other_404_is_an_error(self):
        self.get.return_value = self.response(404, {"error": "not_found", "error_description": "not found"})
        self.assertEqual(client.search_items("商品"), [])
        self.get.return_value = self.response(404, {"message": "unknown route"})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")

    def test_rate_limit_retries_are_bounded_and_respect_retry_after(self):
        self.get.side_effect = [self.response(429, {}, {"Retry-After": "2"}), self.response(200, {"Items": []})]
        self.assertEqual(client.search_items("商品"), [])
        self.sleep.assert_called_once_with(2.0)
        self.assertEqual(self.get.call_count, 2)

    def test_long_retry_after_does_not_send_an_early_retry(self):
        self.get.return_value = self.response(429, {"error": "too_many_requests"}, {"Retry-After": "120"})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_timeout_and_missing_keys_remain_acquisition_errors(self):
        self.get.side_effect = client.requests.Timeout("secret request URL")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError) as caught:
            client.search_items("商品")
        self.assertNotIn("secret request URL", str(caught.exception))
        self.get.reset_mock()
        with patch.dict(os.environ, {"RAKUTEN_WEB_SERVICE_ACCESS_KEY": ""}), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
