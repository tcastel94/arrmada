"""Get Docker container mounts from Unraid — save to file.

Usage: python scripts/test_unraid.py
Requires UNRAID_URL and UNRAID_API_KEY in the .env file.
"""
import asyncio
import json
import os

import httpx

UNRAID_URL = os.getenv("UNRAID_URL", "http://your-unraid:15000")
API_KEY = os.getenv("UNRAID_API_KEY", "")

QUERY = """
{
  docker {
    containers {
      names
      state
      mounts
    }
  }
}
"""

async def main():
    if not API_KEY:
        print("ERROR: Set UNRAID_API_KEY environment variable")
        return

    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        r = await client.post(
            f"{UNRAID_URL}/graphql",
            json={"query": QUERY},
            headers={"Content-Type": "application/json", "x-api-key": API_KEY},
        )
        data = r.json()

        if "errors" in data:
            with open("scripts/mounts.txt", "w") as f:
                f.write(f"Errors: {json.dumps(data['errors'], indent=2)}\n")
            return

        containers = data.get("data", {}).get("docker", {}).get("containers", [])
        service_types = ["radarr", "sonarr", "sabnzbd", "prowlarr", "jellyfin", "bazarr"]

        lines = []
        for c in containers:
            name = (c.get("names") or ["unknown"])[0].lstrip("/").lower()
            matched_service = None
            for svc in service_types:
                if svc in name:
                    matched_service = svc
                    break
            if not matched_service:
                continue

            lines.append(f"\n{'='*70}")
            lines.append(f"Container: {name} ({matched_service}) - {c.get('state')}")

            mounts = c.get("mounts", [])
            for m in mounts:
                if isinstance(m, dict):
                    src = m.get("Source", "?")
                    dst = m.get("Destination", "?")
                    rw = m.get("RW", "?")
                    lines.append(f"  HOST: {src}")
                    lines.append(f"  CONT: {dst}")
                    lines.append(f"  RW: {rw}")
                    lines.append("")

        with open("scripts/mounts.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Wrote {len(lines)} lines to scripts/mounts.txt")

asyncio.run(main())
