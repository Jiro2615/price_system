"""Optional image metadata, in the caller's existing product-save transaction.

No DDL or image downloads in a price worker. Older databases keep working.
"""
from datetime import datetime, timezone
import threading
import time
from urllib.parse import urlsplit

_lock = threading.Lock()
_schema = (0.0, False)
IMAGE_HOSTS = frozenset({"m.media-amazon.com", "images-na.ssl-images-amazon.com",
                         "images-fe.ssl-images-amazon.com", "images-eu.ssl-images-amazon.com"})


def valid_image_url(value):
    try:
        url = str(value or "").strip()
        parsed = urlsplit(url)
        return (len(url) <= 2048 and parsed.scheme == "https" and parsed.hostname in IMAGE_HOSTS
                and not parsed.username and not parsed.password and parsed.port in (None, 443)
                and parsed.path.startswith("/images/") and not parsed.fragment)
    except ValueError:
        return False


def record_main_image(cur, data):
    """Only a verified page observation may replace an earlier observation."""
    global _schema
    observed = data.get("amazon_main_image_checked_at")
    if not observed or data.get("amazon_main_image_verified_asin") != data.get("asin"):
        return
    try:
        observed = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return
    except (TypeError, ValueError):
        return
    url = str(data.get("amazon_main_image_url") or "").strip()
    error = str(data.get("amazon_main_image_error") or "")[:120]
    if not valid_image_url(url):
        url = ""
        error = error or "main_image_unavailable"
    # Recheck after five minutes so applying the central migration needs no
    # worker restart solely to invalidate a negative capability cache.
    with _lock:
        if time.monotonic() >= _schema[0]:
            cur.execute("""SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='amazon_products'
                AND column_name = ANY(%s)""", (["amazon_main_image_url", "amazon_main_image_checked_at",
                                               "amazon_main_image_error"],))
            supported = len(cur.fetchall()) == 3
            _schema = (time.monotonic() + 300, supported)
        supported = _schema[1]
    if not supported:
        return
    cur.execute("""UPDATE amazon_products SET amazon_main_image_url=%s,
        amazon_main_image_checked_at=%s,amazon_main_image_error=%s
        WHERE asin=%s AND (amazon_main_image_checked_at IS NULL OR amazon_main_image_checked_at <= %s)""",
                (url, observed.astimezone(timezone.utc), error, data["asin"], observed))
