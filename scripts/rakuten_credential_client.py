"""Central Rakuten credentials, opt-in; no disk cache or implicit fallback."""
import json
import http.client
import os
import re
import threading
import time
import urllib.request
import socket
import stat
from pathlib import Path
from urllib.parse import urlparse

_cache = {}
_lock = threading.Lock()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def unix_credentials(path, parsed, body, headers):
    """Same-host transport only, restricted by filesystem ownership AND token."""
    path = Path(path)
    if not path.is_absolute() or not hasattr(os, "geteuid"):
        raise ValueError("Unix transport unavailable")
    for target, mode in ((path.parent, 0o700), (path, 0o600)):
        info = target.lstat()
        if target.is_symlink() or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != mode:
            raise ValueError("Unix transport permissions invalid")
    if not stat.S_ISSOCK(path.stat().st_mode):
        raise ValueError("Unix transport requires socket")
    connection = http.client.HTTPConnection(parsed.hostname, timeout=15)
    connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.sock.settimeout(15)
    try:
        connection.sock.connect(str(path))
        connection.request("POST", parsed.path, body, {**headers, "X-Forwarded-Proto": "https"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Unix transport access denied")
        return json.loads(response.read(8192))
    finally:
        connection.close()


def central_credentials(store):
    url = os.getenv("RAKUTEN_CREDENTIAL_URL", "").strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("Central Rakuten credential URL must be HTTPS without URL credentials")
    store = str(store or "").strip().lower()
    if not re.fullmatch(r"rakuten_[a-z0-9_]+", store):
        raise RuntimeError("Central Rakuten credentials require an explicit store")
    token = os.getenv("RAKUTEN_CREDENTIAL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Central Rakuten credential token is missing")
    unix_socket = os.getenv("RAKUTEN_CREDENTIAL_UNIX_SOCKET", "").strip()
    key = (url, store, token, unix_socket)
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < 30:
            return dict(cached[1])
        try:
            body = json.dumps({"action": "read", "store": store}).encode()
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
            if unix_socket:
                data = unix_credentials(unix_socket, parsed, body, headers)
            else:
                request = urllib.request.Request(url, data=body, headers=headers, method="POST")
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
                with opener.open(request, timeout=15) as response:
                    data = json.loads(response.read(8192))
            result = {k: data[k] for k in ("service_secret", "license_key")}
            if not all(isinstance(v, str) and v.strip() for v in result.values()):
                raise ValueError()
        except Exception:
            raise RuntimeError("Central Rakuten credential retrieval failed; no local fallback") from None
        _cache.clear()
        _cache[key] = (time.monotonic(), result)
        return dict(result)
