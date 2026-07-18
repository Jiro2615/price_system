
from __future__ import annotations

import secrets
from datetime import datetime

from scripts.listing.models import ManagementNumberBundle


def generate_management_number_bundle(management_suffix: str = "187", now: datetime | None = None) -> ManagementNumberBundle:
    now = now or datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    legacy_candidate = f"{timestamp}_{management_suffix}"
    safe_candidate = f"{legacy_candidate}_{secrets.token_hex(2)}"
    return ManagementNumberBundle(
        selected=safe_candidate,
        legacy_candidate=legacy_candidate,
        safe_candidate=safe_candidate,
        note="dry-run uses a collision-safe candidate; legacy format is kept for compatibility notes only",
    )


def build_management_number_bundle_from_selected(selected: str) -> ManagementNumberBundle:
    normalized = str(selected or "").strip()
    if not normalized:
        raise ValueError("selected management number is required")
    parts = normalized.split("_")
    legacy_candidate = normalized
    if len(parts) >= 3:
        legacy_candidate = "_".join(parts[:-1])
    return ManagementNumberBundle(
        selected=normalized,
        legacy_candidate=legacy_candidate,
        safe_candidate=normalized,
        note="explicit management number provided by operator; legacy candidate derived from selected value",
    )
