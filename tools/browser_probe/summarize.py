"""Offline report: never treats missing or failed observations as a pass."""
import json
from pathlib import Path
import statistics
import sys
import re
from datetime import datetime


def comparable(value):
    if isinstance(value, str):
        value = re.sub(r"\s+", " ", value).strip()
        return re.sub(r"[（(]\s*\d+\s*時間\s*\d+\s*分以内にご注文の場合\s*[）)]", "(COUNTDOWN)", value)
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def compare_cases(a, b):
    valid = bool(a.get("baseline") and b.get("baseline") and not a.get("error") and not b.get("error")
                 and not a["baseline"].get("system_error") and not b["baseline"].get("system_error"))
    keys = set(a.get("baseline", {})) | set(b.get("baseline", {}))
    differences = sorted(k for k in keys if comparable(a.get("baseline", {}).get(k)) != comparable(b.get("baseline", {}).get(k)))
    return {"valid": valid, "baseline_matches": valid and not differences,
            "baseline_differences": differences,
            "captured_offers_match_except_countdown": bool(a.get("offers") and b.get("offers")) and comparable(a.get("offers")) == comparable(b.get("offers")),
            "necessary_offers_loaded_both": a.get("required_offers_loaded") is True and b.get("required_offers_loaded") is True}


def summarize(folder):
    runs = []
    raw = {}
    for path in sorted(folder.glob("round*_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        raw[path.stem] = data
        cases = data.get("cases", [])
        tested = set(c["asin"] for c in cases)
        samples = data.get("resource_samples", [])
        # Compare first/last quartile AFTER initial warmup, not launch/teardown.
        warm = [s for s in samples if s["seconds"] >= 60]
        width = max(1, len(warm)//4)
        start = statistics.median(s["uss_mib"] for s in warm[:width]) if warm else None
        end = statistics.median(s["uss_mib"] for s in warm[-width:]) if warm else None
        runs.append({"file": path.name, "mode": data["mode"], "version": data.get("version"),
                     "complete": bool(data.get("metrics") and cases and not data.get("error") and not data.get("stopped")),
                     "cases": len(cases), "errors": [c.get("error") for c in cases if c.get("error")],
                     "distinct_asins_tested": len(tested),
                     "all_selected_asins_tested": bool(tested) and not (set(data.get("asins", [])) - tested),
                     "untested_asins": sorted(set(data.get("asins", [])) - tested),
                     "insufficient_offers": [c["index"] for c in cases if not c.get("required_offers_loaded")],
                     "unknown_total_count": [c["index"] for c in cases if not c.get("count_known")],
                     "changed_after_navigation": [c["index"] for c in cases if not c.get("same_after_navigation")],
                     "metrics": data.get("metrics"),
                     "warm_uss_start_mib": start, "warm_uss_end_mib": end,
                     "warm_uss_change_mib": None if start is None else round(end-start, 2)})
    machine = json.loads((folder / "machine.json").read_text(encoding="utf-8"))
    expected = machine["arguments"]["rounds"] * 2
    pairs = []
    for repetition in range(1, machine["arguments"]["rounds"] + 1):
        a = raw.get(f"round{repetition}_chrome", {}).get("cases", [])
        b = raw.get(f"round{repetition}_shell", {}).get("cases", [])
        for index in range(max(len(a), len(b))):
            ca = a[index] if index < len(a) else {}
            cb = b[index] if index < len(b) else {}
            gap = abs((datetime.fromisoformat(ca["utc"]) - datetime.fromisoformat(cb["utc"])).total_seconds()) if ca.get("utc") and cb.get("utc") else None
            pairs.append({"round": repetition, "index": index, "asin": ca.get("asin") or cb.get("asin"),
                          "start_time_gap_seconds": gap,
                          "same_asin": bool(ca.get("asin")) and ca.get("asin") == cb.get("asin"),
                          **compare_cases(ca, cb)})
    result = {"expected_runs": expected, "observed_runs": len(runs),
              "all_runs_complete": len(runs) == expected and all(r["complete"] for r in runs),
              "all_selected_asins_tested_in_each_run": len(runs) == expected and all(r["all_selected_asins_tested"] for r in runs),
              "paired_observations": pairs,
              "note": "Memory growth is not by itself proof of a leak. Review raw per-ASIN results for time-varying prices and delivery. No automatic production adoption.",
              "runs": runs}
    (folder / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    summarize(Path(sys.argv[1]))
