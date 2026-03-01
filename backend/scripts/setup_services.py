"""Script to add services and run health checks.

Usage: python scripts/setup_services.py

Reads credentials from environment variables or prompts interactively.
"""
import os
import httpx

BASE = os.getenv("ARRMADA_API_URL", "http://localhost:8000")
PASSWORD = os.getenv("ARRMADA_AUTH_SECRET", "")

if not PASSWORD:
    PASSWORD = input("ArrMada password: ")

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"password": PASSWORD})
r.raise_for_status()
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Example services — replace with your own URLs and API keys
services = [
    {"name": "Radarr",   "type": "radarr",   "url": "http://your-server:7878", "api_key": "your-radarr-api-key"},
    {"name": "Sonarr",   "type": "sonarr",   "url": "http://your-server:8989", "api_key": "your-sonarr-api-key"},
    {"name": "Bazarr",   "type": "bazarr",   "url": "http://your-server:6767", "api_key": "your-bazarr-api-key"},
    {"name": "Prowlarr", "type": "prowlarr", "url": "http://your-server:9696", "api_key": "your-prowlarr-api-key"},
    {"name": "Jellyfin", "type": "jellyfin", "url": "http://your-server:8096", "api_key": "your-jellyfin-api-key"},
    {"name": "SABnzbd",  "type": "sabnzbd",  "url": "http://your-server:8080", "api_key": "your-sabnzbd-api-key"},
]

for svc in services:
    r = httpx.post(f"{BASE}/api/services", headers=headers, json=svc)
    name = svc["name"]
    print(f"{name}: {r.status_code}")

print("\n--- Health Checks ---")
r = httpx.get(f"{BASE}/api/services/health/all", headers=headers, timeout=15)
for h in r.json():
    name = h["service_name"]
    status = h["status"]
    latency = h.get("latency_ms", "?")
    version = h.get("version", "?")
    error = h.get("error", "")
    print(f"{name}: {status} ({latency}ms) v{version} {error}")

print("\n--- Dashboard Stats ---")
r = httpx.get(f"{BASE}/api/dashboard/stats", headers=headers, timeout=30)
print(r.json())
