"""Docker HEALTHCHECK: GET /api/health through the public gateway.

Going through the gateway checks the whole chain (proxy + API) at once.
Exit 0 = healthy, 1 = unhealthy (Docker's convention).
"""

import os
import sys
import urllib.request

port = os.environ.get("ARRMADA_PORT", "3420")
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception as exc:  # noqa: BLE001 — any failure means unhealthy
    print(f"unhealthy: {exc}", file=sys.stderr)
    sys.exit(1)
