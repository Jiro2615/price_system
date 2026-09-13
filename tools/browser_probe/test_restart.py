import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from probe_support import atomic_json
from restart_probe import run_cycles, remaining_processes


class RestartTests(unittest.TestCase):
    def test_three_counted_cycles_same_python(self):
        calls = []
        async def fake(mode, path, **kw):
            calls.append(kw)
            from restart_probe import process_snapshot
            atomic_json(path, {"cases": [{"index": kw["index_offset"]+i, "asin": asin}
                for i, asin in enumerate(kw["plan"])], "before_close": process_snapshot()})
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "result.json"
            asyncio.run(run_cycles(fake, "chrome", out, ["B07QP2L8LC", "B019SKZXV8", "B0F2HTH5H9"], 50, 3))
            data = json.loads(out.read_text())
            self.assertEqual(len(data["cases"]), 150)
            self.assertEqual([c["index_offset"] for c in calls], [0, 50, 100])
            self.assertTrue(all(c["cleanup_verified"] for c in data["cycles"]))
            self.assertNotIn("error", data)

    def test_incomplete_cycle_stops(self):
        async def fake(mode, path, **kw):
            atomic_json(path, {"cases": [], "stopped": True})
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "result.json"
            asyncio.run(run_cycles(fake, "chrome", out, ["B07QP2L8LC"], 50, 3))
            data = json.loads(out.read_text())
            self.assertTrue(data["stopped"])
            self.assertEqual(len(data["cycles"]), 1)
            self.assertFalse(data["cycles"][0]["cleanup_verified"])

    def test_pid_reuse_not_residual(self):
        with patch("restart_probe.psutil.Process") as process:
            process.return_value.create_time.return_value = 2
            self.assertEqual(remaining_processes({"processes": [{"pid": 123, "created": 1}]}, {"processes": []}), [])


if __name__ == "__main__":
    unittest.main()
