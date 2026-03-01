"""Fix duplicate movie spam — remove duplicate from Radarr and clean request.

Usage: python scripts/fix_dune_spam.py

This is a one-off maintenance script. Set ARRMADA_AUTH_SECRET and
RADARR_API_KEY environment variables before running.
"""
import os
import httpx

BASE = os.getenv("ARRMADA_API_URL", "http://localhost:8000")
PASSWORD = os.getenv("ARRMADA_AUTH_SECRET", "")
RADARR_API_KEY = os.getenv("RADARR_API_KEY", "")

if not PASSWORD:
    PASSWORD = input("ArrMada password: ")
if not RADARR_API_KEY:
    RADARR_API_KEY = input("Radarr API key: ")

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"password": PASSWORD})
r.raise_for_status()
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 1. Delete the request from ArrMada
print("=== Cleaning ArrMada requests ===")
r = httpx.get(f"{BASE}/api/requests", headers=headers)
requests_data = r.json()
for req in requests_data["items"]:
    if "dune" in req["title"].lower():
        print(f"Deleting request: {req['title']} (id={req['id']}, arr_id={req['arr_id']})")
        httpx.delete(f"{BASE}/api/requests/{req['id']}", headers=headers)

# 2. Check Radarr directly for duplicates
print("\n=== Checking Radarr for Dune Part Two ===")
r = httpx.get(f"{BASE}/api/services", headers=headers)
services = r.json()
radarr_svc = next((s for s in services if s["type"] == "radarr"), None)

if radarr_svc:
    radarr_url = radarr_svc["url"]

    r = httpx.get(
        f"{radarr_url}/api/v3/movie",
        params={"apikey": RADARR_API_KEY},
        timeout=10,
    )
    movies = r.json()

    dune_movies = [m for m in movies if "dune" in m.get("title", "").lower() and "two" in m.get("title", "").lower()]
    print(f"Found {len(dune_movies)} Dune Part Two entries:")

    for m in dune_movies:
        has_file = m.get("hasFile", False)
        movie_id = m["id"]
        print(f"  - id={movie_id}, title={m['title']}, hasFile={has_file}, monitored={m.get('monitored')}")

        if not has_file:
            print(f"    -> Deleting duplicate (no file) id={movie_id}")
            httpx.delete(
                f"{radarr_url}/api/v3/movie/{movie_id}",
                params={"apikey": RADARR_API_KEY, "deleteFiles": "false"},
                timeout=10,
            )
            print(f"    -> Deleted!")
        else:
            print(f"    -> Keeping (has file)")

print("\nDone! Spam should stop now.")
