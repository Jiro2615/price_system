
from __future__ import annotations

import secrets
from datetime import datetime

from .models import ManagementNumberBundle


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
