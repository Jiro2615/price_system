"""Count-driven full-browser cycles. Python survives across all cycles."""
import asyncio
import json
import time

from probe_support import Meter, atomic_json, psutil


def process_snapshot():
    root = psutil.Process()
    items = []
    for proc in [root] + root.children(recursive=True):
        try:
            items.append({"pid": proc.pid, "created": proc.create_time(),
                          "uss_mib": round(proc.memory_full_info().uss / 2**20, 2)})
        except psutil.NoSuchProcess:
            pass
    return {"uss_mib": round(sum(p["uss_mib"] for p in items), 2), "processes": items}


def remaining_processes(old, baseline):
    excluded = {(p["pid"], p["created"]) for p in baseline["processes"]}
    remaining = []
    for item in old["processes"]:
        if (item["pid"], item["created"]) in excluded:
            continue
        try:
            proc = psutil.Process(item["pid"])
            if proc.create_time() == item["created"] and proc.is_running():
                remaining.append(item)
        except psutil.NoSuchProcess:
            pass
    return remaining


async def run_cycles(run, mode, out, plan, every, cycles, sync=None, first="chrome"):
    result = {"mode": mode, "profile": "single_read_restart", "asins": list(dict.fromkeys(plan)),
              "cases": [], "cycles": [], "requested_cases": every * cycles,
              "restart_every": every, "requested_cycles": cycles}
    cycle_dir = out.parent / (out.stem + "_cycles")
    cycle_dir.mkdir(exist_ok=True)
    meter = Meter(out.with_suffix(".resources.json"))
    meter.start()
    atomic_json(out, result)
    try:
        for index in range(cycles):
            if (out.parent / "STOP").exists() or (sync and (sync / "STOP").exists()):
                result["stopped"] = True
                break
            offset = index * every
            cycle_plan = [plan[(offset + n) % len(plan)] for n in range(every)]
            before = process_snapshot()
            path = cycle_dir / f"cycle{index+1}.json"
            # The shared sync STOP is monitored during each product. A parent
            # STOP is forwarded by the existing parent supervisor.
            await run(mode, path, plan=cycle_plan, sync=sync, first=first,
                      case_limit=every, index_offset=offset)
            data = json.loads(path.read_text(encoding="utf-8"))
            old = data.get("before_close", before)
            deadline = time.monotonic() + 5
            remaining = remaining_processes(old, before)
            while remaining and time.monotonic() < deadline:
                await asyncio.sleep(.2)
                remaining = remaining_processes(old, before)
            result["cases"].extend(data.get("cases", []))
            result["version"] = data.get("version")
            result["cycles"].append({"cycle": index+1, "cases": len(data.get("cases", [])),
                "metrics": data.get("metrics"), "before_launch": before,
                "before_close": old, "after_close": process_snapshot(),
                "remaining_processes": remaining, "cleanup_verified": "before_close" in data and not remaining})
            if data.get("stopped"):
                result["stopped"] = True
            if data.get("error") or remaining or "before_close" not in data or len(data.get("cases", [])) != every:
                result["error"] = data.get("error") or "Incomplete cycle or unverified process cleanup"
            atomic_json(out, result)
            if result.get("error") or result.get("stopped"):
                break
    except asyncio.CancelledError:
        result["stopped"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["metrics"] = meter.finish()
        result["resource_samples"] = meter.resource_samples()
        atomic_json(out, result)
        if sync:
            if result.get("error") or result.get("stopped"):
                (sync / "STOP").touch()
            (sync / f"{mode}.finished").touch()
