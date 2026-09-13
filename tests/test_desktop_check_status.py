import ast
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "desktop_check_status.py"
spec = importlib.util.spec_from_file_location("desktop_check_status", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DesktopStatusTests(unittest.TestCase):
    def test_disabled_does_not_launch(self):
        with patch.object(module.subprocess, "Popen") as launch:
            status = module.DesktopCheckStatus()
            status.update(1, 50)
            status.close()
            launch.assert_not_called()

    def test_updates_and_eof_cleanup(self):
        process = Mock()
        process.poll.return_value = None
        status = module.DesktopCheckStatus()
        status.process = process
        status.update(2, 50, "B07QP2L8LC")
        self.assertIn("B07QP2L8LC", process.stdin.write.call_args.args[0])
        status.close()
        process.stdin.close.assert_called_once()
        process.wait.assert_called_once_with(timeout=1)
        status.close()

    def test_manual_close_does_not_reopen_or_write(self):
        process = Mock()
        process.poll.return_value = 0
        status = module.DesktopCheckStatus()
        status.process = process
        status.update(3, 50)
        process.stdin.write.assert_not_called()

    def test_broken_pipe_is_nonfatal(self):
        process = Mock()
        process.poll.return_value = None
        process.stdin.write.side_effect = BrokenPipeError()
        status = module.DesktopCheckStatus()
        status.process = process
        status.update(3, 50)
        self.assertIsNone(status.process)

    def test_cleanup_timeout_is_nonfatal(self):
        process = Mock()
        process.wait.side_effect = TimeoutError()
        status = module.DesktopCheckStatus()
        status.process = process
        status.close()
        process.terminate.assert_called_once()

    def test_launch_failure_is_nonfatal(self):
        with patch.object(module.os, "name", "nt"), patch.object(
            module.subprocess, "Popen", side_effect=OSError("unavailable")
        ):
            module.DesktopCheckStatus(enabled=True).update(0, 50)

    def test_worker_integration(self):
        tree = ast.parse((SCRIPT.parent / "price_check_from_db.py").read_text(encoding="utf-8"))
        main = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "main")
        text = ast.unparse(main)
        self.assertIn("DesktopCheckStatus(enabled=args.browser == 'shell')", text)
        self.assertIn("desktop_status.update(idx - 1, len(asins), asin", text)
        self.assertIn("desktop_status.update(idx, len(asins), asin", text)
        self.assertIn("finally:\n            desktop_status.close()", text)


if __name__ == "__main__":
    unittest.main()
