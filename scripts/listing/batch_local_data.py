"""Run-scoped local data, shared by preparation threads, never a global cache."""
from __future__ import annotations

import asyncio
from copy import copy, deepcopy
from pathlib import Path
from threading import RLock
from time import monotonic

from scripts.listing.master_loader import load_active_master_data
from scripts.listing.listing_duplicate_check import find_existing_listings


class BatchLocalData:
    """Bounded staleness during screening; live execution revalidates uncached.

    Keys are run/store specific. Failed refreshes propagate (no stale fallback).
    Only rule structures read-only to evaluators are shared; mutable ASIN
    exceptions are assigned to a separate MasterData shell for every caller.
    """
    def __init__(self, store_code: str, master_dir: Path, asins: list[str],
                 allow_missing: bool = False, *, ttl: float = 30.0,
                 clock=monotonic, master_loader=load_active_master_data,
                 duplicate_loader=find_existing_listings):
        self.store_code = store_code
        self.master_dir = Path(master_dir)
        self.asins = list(dict.fromkeys(asin.strip().upper() for asin in asins))
        self._asin_set = frozenset(self.asins)
        self.allow_missing = allow_missing
        self.ttl = ttl
        self.clock = clock
        self.master_loader = master_loader
        self.duplicate_loader = duplicate_loader
        self._lock = RLock()
        self._values = {}

    def _get(self, key, loader):
        with self._lock:
            entry = self._values.get(key)
            if entry is None or self.clock() - entry[0] >= self.ttl:
                value = loader()
                entry = (self.clock(), value)
                self._values[key] = entry
            return entry[1]

    def masters(self):
        value = self._get("masters", lambda: self.master_loader(
            self.master_dir, self.store_code, self.allow_missing))
        result = copy(value)
        result.allowed_phrase_rules = deepcopy(value.allowed_phrase_rules)
        result.allowed_phrase_meta = deepcopy(value.allowed_phrase_meta)
        return result

    def existing(self, asin: str, store_code: str):
        if store_code != self.store_code or asin.strip().upper() not in self._asin_set:
            raise ValueError("ASIN/store outside batch local-data scope")
        values = self._get("duplicates", lambda: self.duplicate_loader(self.asins, self.store_code))
        return copy(values.get(asin.strip().upper()))

    def settings(self, loader):
        return deepcopy(self._get("settings", lambda: loader(self.store_code)))

    def common_settings(self, loader, store_settings):
        return deepcopy(self._get("common", lambda: loader(store_settings)))

    def validate_scope(self, request):
        if (request.offline or request.store_code != self.store_code
                or Path(request.master_dir) != self.master_dir
                or request.allow_missing_master != self.allow_missing
                or request.store_settings_json is not None):
            raise ValueError("Incompatible batch local-data scope")


class LazyAmazonPages:
    """No browser startup at all for a batch rejected by local/Keepa checks."""
    def __init__(self, factory, workers):
        self.factory = factory
        self.workers = workers
        self._lock = asyncio.Lock()
        self._pages = None
        self._error = None
        self._resources = None

    async def get(self, tab_number):
        async with self._lock:
            if self._error is not None:
                raise RuntimeError("Amazon browser initialization failed") from self._error
            if self._pages is None:
                try:
                    self._resources = await self.factory()
                    playwright, browser, context, page = self._resources
                    pages = [page]
                    for _ in range(1, self.workers):
                        pages.append(await context.new_page())
                    self._pages = pages
                except Exception as exc:
                    self._error = exc
                    raise
            return self._pages[tab_number - 1]
