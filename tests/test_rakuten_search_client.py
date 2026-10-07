"""No external HTTP, IP lookup, dotenv reads, real sleeping, or DB writes."""
import contextlib
import io
import os
import unittest
from email.utils import formatdate
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
        self.slot = self.stack.enter_context(patch.object(client, "_wait_for_slot", return_value=0.0))
        self.defer = self.stack.enter_context(patch.object(client, "_defer_requests"))
        self.jitter = self.stack.enter_context(patch.object(client.random, "uniform", return_value=0.0))
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

    def test_rate_limit_retries_five_times_with_exponential_backoff(self):
        self.get.return_value = self.response(429, {"error": "too_many_requests"}, {"Retry-After": "1"})
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(client.RakutenSearchError) as caught:
            client.search_items("商品")
        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(self.get.call_count, 6)
        self.assertEqual([call.args[0] for call in self.sleep.call_args_list], [2.0, 4.0, 8.0, 16.0, 32.0])
        self.assertEqual(output.getvalue().count("RAKUTEN_SEARCH_RETRY"), 5)
        self.assertEqual([call.kwargs["max_wait_seconds"] for call in self.slot.call_args_list],
                         [90.0, 88.0, 84.0, 76.0, 60.0, 28.0])

    def test_success_on_the_last_attempt_returns_items_instead_of_error(self):
        self.get.side_effect = [self.response(429, {}) for _ in range(5)] + [self.response(200, {"items": [{"itemName": "商品"}]})]
        self.assertEqual(client.search_items("商品"), [{"itemName": "商品"}])
        self.assertEqual(self.get.call_count, 6)

    def test_jitter_is_added_to_break_simultaneous_retries(self):
        self.jitter.return_value = 0.75
        self.get.side_effect = [self.response(429, {}), self.response(200, {"items": []})]
        self.assertEqual(client.search_items("商品"), [])
        self.sleep.assert_called_once_with(2.75)
        self.defer.assert_called_once_with(2.75)

    def test_response_body_delay_is_respected_when_header_is_missing(self):
        self.get.side_effect = [self.response(429, {"errors": {"errorMessage": "Rate limit is exceeded. Try again in 7 seconds."}}),
                                self.response(200, {"items": []})]
        self.assertEqual(client.search_items("商品"), [])
        self.sleep.assert_called_once_with(7.0)

    def test_retry_after_date_is_respected(self):
        now = 1700000000.0
        self.get.side_effect = [self.response(429, {}, {"Retry-After": formatdate(now + 20, usegmt=True)}),
                                self.response(200, {"items": []})]
        with patch.object(client.time, "time", return_value=now):
            self.assertEqual(client.search_items("商品"), [])
        self.sleep.assert_called_once_with(20.0)

    def test_longer_header_wins_over_a_shorter_body_delay(self):
        self.get.side_effect = [self.response(429, {"message": "Try again in 1 seconds."}, {"Retry-After": "10"}),
                                self.response(200, {"items": []})]
        self.assertEqual(client.search_items("商品"), [])
        self.sleep.assert_called_once_with(10.0)

    def test_wait_budget_stops_before_an_early_or_excessive_retry(self):
        self.get.return_value = self.response(429, {}, {"Retry-After": "50"})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.assertEqual(self.get.call_count, 2)
        self.sleep.assert_called_once_with(50.0)
        self.defer.assert_called_with(50.0)

    def test_slot_waits_share_the_same_wait_budget(self):
        self.slot.return_value = 89.0
        self.get.return_value = self.response(429, {})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_invalid_retry_headers_fall_back_to_bounded_backoff(self):
        for header in ("NaN", "Infinity", "bad header", "-1"):
            with self.subTest(header=header):
                self.get.reset_mock()
                self.sleep.reset_mock()
                self.get.side_effect = [self.response(429, {}, {"Retry-After": header}), self.response(200, {"items": []})]
                self.assertEqual(client.search_items("商品"), [])
                self.sleep.assert_called_once_with(2.0)

    def test_non_json_rate_limit_response_is_retried_but_not_treated_as_empty_items(self):
        invalid = self.response(429, {})
        invalid.json.side_effect = ValueError("not JSON")
        self.get.side_effect = [invalid, self.response(200, {"items": []})]
        self.assertEqual(client.search_items("商品"), [])
        self.assertEqual(self.get.call_count, 2)

    def test_other_status_errors_are_not_retried(self):
        for status in (400, 401, 403, 500, 503):
            with self.subTest(status=status):
                self.get.reset_mock()
                self.get.return_value = self.response(status, {"error": "denied"}, {"Retry-After": "1"})
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
                    client.search_items("商品")
                self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_retries_stop_on_keyboard_interrupt(self):
        self.get.return_value = self.response(429, {})
        self.sleep.side_effect = KeyboardInterrupt()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            client.search_items("商品")
        self.get.assert_called_once()

    def test_retry_logs_do_not_expose_keys_url_or_search_text(self):
        self.get.return_value = self.response(429, {"message": "fake-app fake-secret-key-for-client-tests https://example.com/private"})
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(client.RakutenSearchError):
            client.search_items("private-search-text")
        for secret in ("fake-app", "fake-secret-key-for-client-tests", "https://", "private-search-text"):
            self.assertNotIn(secret, output.getvalue())

    def test_long_retry_after_does_not_send_an_early_retry(self):
        self.get.return_value = self.response(429, {"error": "too_many_requests"}, {"Retry-After": "120"})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.get.assert_called_once()
        self.sleep.assert_not_called()
        self.defer.assert_called_once_with(120.0)

    def test_timeout_and_missing_keys_remain_acquisition_errors(self):
        self.get.side_effect = client.requests.Timeout("secret request URL")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError) as caught:
            client.search_items("商品")
        self.assertNotIn("secret request URL", str(caught.exception))
        self.get.reset_mock()
        with patch.dict(os.environ, {"RAKUTEN_WEB_SERVICE_ACCESS_KEY": ""}), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client.search_items("商品")
        self.get.assert_not_called()


class LocalCooldownTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.sleeps = []
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(client, "_next_request_at", 0.0))
        self.stack.enter_context(patch.object(client, "_logged_errors", {}))
        self.stack.enter_context(patch.object(client.time, "monotonic", side_effect=lambda: self.now))
        self.stack.enter_context(patch.object(client.time, "sleep", side_effect=self.advance))

    def advance(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def test_requests_keep_one_second_spacing(self):
        self.assertEqual(client._wait_for_slot(), 0.0)
        self.assertEqual(client._wait_for_slot(), 1.0)
        self.assertEqual(client._wait_for_slot(), 1.0)
        self.assertEqual(self.sleeps, [1.0, 1.0])
        self.assertEqual(client._next_request_at, 3.0)

    def test_cooldown_extension_during_a_wait_is_rechecked_without_holding_lock(self):
        client._next_request_at = 5.0
        def extend_once(seconds):
            acquired = client._slot_lock.acquire(blocking=False)
            self.assertTrue(acquired, "Wait must not hold the slot lock")
            if acquired:
                client._slot_lock.release()
            if not self.sleeps:
                client._defer_requests(7.0)
            self.advance(seconds)
        with patch.object(client.time, "sleep", side_effect=extend_once):
            self.assertEqual(client._wait_for_slot(), 7.0)
        self.assertEqual(self.sleeps, [5.0, 2.0])
        self.assertEqual(client._next_request_at, 8.0)

    def test_a_shorter_cooldown_cannot_shorten_an_existing_deadline(self):
        client._next_request_at = 10.0
        client._defer_requests(3.0)
        self.assertEqual(client._next_request_at, 10.0)
        client._defer_requests(15.0)
        self.assertEqual(client._wait_for_slot(), 15.0)

    def test_long_cooldown_fails_without_sleeping_or_sending_early(self):
        client._defer_requests(120.0)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError) as caught:
            client._wait_for_slot()
        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.code, "rate_limit_cooldown")
        self.assertEqual(self.sleeps, [])

    def test_wait_budget_is_checked_again_after_an_extension(self):
        client._next_request_at = 2.0
        def extend(seconds):
            if not self.sleeps:
                client._defer_requests(20.0)
            self.advance(seconds)
        with patch.object(client.time, "sleep", side_effect=extend), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(client.RakutenSearchError):
            client._wait_for_slot(max_wait_seconds=10.0)
        self.assertEqual(self.sleeps, [2.0])


if __name__ == "__main__":
    unittest.main()
