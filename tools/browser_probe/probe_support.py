"""Isolated read-only Amazon resource probe; never runs a worker or persists to DB."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "deps"))
import psutil

ASIN = "B07QP2L8LC"  # Mandatory regression subject requested by the user.
REPO = ROOT.parents[1]
FIELDS = ("asin", "title", "amazon_price", "amazon_point", "available_qty",
          "minimum_order_quantity", "gift_available", "shipping_status",
          "business_ng", "system_error", "ng_reason", "selected_offer")
SELECTORS = {"title": "#productTitle", "price": "#corePriceDisplay_desktop_feature_div",
             "availability": "#availability", "merchant": "#merchant-info",
             "buybox": "#buybox", "delivery": "#deliveryBlockMessage",
             "destination": "#glow-ingress-line2", "offers": "#aod-offer-list"}


class Meter:
    """Sample only this test's process tree; shared RSS is not physical usage."""
    def __init__(self):
        self.root = psutil.Process()
        self.stop_event = threading.Event()
        self.last = {}
        self.cpu = 0.0
        self.rows = []
        self.started = time.monotonic()
        t = self.root.cpu_times()
        self.last[(self.root.pid, self.root.create_time())] = t.user + t.system
        self.thread = threading.Thread(target=self.run, daemon=True)

    def sample(self):
        rss = private = count = uss = 0
        try:
            processes = [self.root] + self.root.children(recursive=True)
        except psutil.Error:
            processes = [self.root]
        for process in processes:
            try:
                key = process.pid, process.create_time()
                t = process.cpu_times()
                cpu = t.user + t.system
                self.cpu += max(0.0, cpu - self.last.get(key, 0.0))
                self.last[key] = cpu
                m = process.memory_full_info()
                rss += m.rss
                private += getattr(m, "private", m.vms)
                uss += m.uss
                count += 1
            except psutil.Error:
                pass
        self.rows.append((rss, private, count, psutil.cpu_percent(), uss, round(time.monotonic() - self.started, 3)))

    def run(self):
        while not self.stop_event.wait(0.2):
            self.sample()

    def start(self):
        psutil.cpu_percent()
        self.sample()
        self.thread.start()

    def finish(self):
        self.stop_event.set()
        self.thread.join()
        self.sample()
        elapsed = time.monotonic() - self.started
        return {"elapsed_seconds": round(elapsed, 3), "cpu_seconds": round(self.cpu, 3),
                "avg_cpu_percent_machine_capacity": round(100 * self.cpu / elapsed / psutil.cpu_count(), 2),
                "peak_private_commit_mib": round(max(r[1] for r in self.rows) / 2**20, 1),
                "peak_summed_rss_mib": round(max(r[0] for r in self.rows) / 2**20, 1),
                "peak_private_working_set_mib": round(max(r[4] for r in self.rows) / 2**20, 1),
                "peak_processes": max(r[2] for r in self.rows),
                "host_avg_cpu_percent": round(sum(r[3] for r in self.rows) / len(self.rows), 1),
                "samples": len(self.rows)}


def no_db(*args, **kwargs):
    raise RuntimeError("DB access is forbidden by this probe")


def challenge(url, body):
    return any(x in url.lower() for x in ("captcha", "/ap/signin")) or any(
        x in body for x in ("下に表示されている文字を入力してください", "Enter the characters you see below", "ロボットではない"))
