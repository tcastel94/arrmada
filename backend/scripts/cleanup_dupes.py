"""Clean up duplicate services."""
import httpx

BASE = "http://localhost:8000"
r = httpx.post(f"{BASE}/api/auth/login", json={"password": "changeme_use_a_strong_password"})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# List services
r = httpx.get(f"{BASE}/api/services", headers=headers)
services = r.json()
print(f"Found {len(services)} services")

# Remove duplicates (keep lowest ID for each type)
seen = {}
for svc in services:
    t = svc["type"]
    if t in seen:
        # Delete the duplicate
        httpx.delete(f"{BASE}/api/services/{svc['id']}", headers=headers)
        print(f"Deleted duplicate: {svc['name']} (id={svc['id']})")
    else:
        seen[t] = svc["id"]
        print(f"Kept: {svc['name']} (id={svc['id']})")
