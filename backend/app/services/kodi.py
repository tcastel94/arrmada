"""Kodi service for discovering instances and triggering library scans."""

import asyncio
import httpx
from typing import List, Dict, Any
from zeroconf import ServiceBrowser, Zeroconf

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

class KodiListener:
    def __init__(self):
        self.found = []

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            ip = ".".join([str(c) for c in info.addresses[0]])
            port = info.port
            url = f"http://{ip}:{port}"
            self.found.append({
                "name": name.split(".")[0],
                "url": url,
            })

    def update_service(self, zeroconf, type, name):
        pass

async def discover_kodi() -> List[Dict[str, str]]:
    """Discover local Kodi instances via ZeroConf (mDNS)."""
    zeroconf = Zeroconf()
    listener = KodiListener()
    
    # Listen for kodi web interfaces
    # Usually Kodi broadcasts _http._tcp.local or _xbmc-jsonrpc._tcp.local
    # Let's check _http._tcp.local
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    
    await asyncio.sleep(3) # Wait for discovery
    
    zeroconf.close()
    
    # Filter for Kodi
    kodi_instances = [s for s in listener.found if "kodi" in s["name"].lower() or "xbmc" in s["name"].lower()]
    return kodi_instances

async def sync_kodi(db: AsyncSession) -> dict[str, Any]:
    """Trigger VideoLibrary.Scan on all registered Kodi instances."""
    stmt = select(Service).where(Service.type == "kodi", Service.is_enabled == True)
    result = await db.execute(stmt)
    kodis = result.scalars().all()
    
    success = 0
    failed = 0
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for kodi in kodis:
            url = f"{kodi.url}/jsonrpc"
            auth = None
            if kodi.api_key:
                # Assuming api_key stores "username:password" explicitly, but wait, it's encrypted
                creds = decrypt_api_key(kodi.api_key)
                if ":" in creds:
                    auth = tuple(creds.split(":", 1))
            
            payload = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.Scan",
                "id": sum(ord(c) for c in kodi.name)
            }
            
            try:
                if auth:
                    resp = await client.post(url, json=payload, auth=auth)
                else:
                    resp = await client.post(url, json=payload)
                    
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    logger.error(f"Kodi sync error on {kodi.name}: {data['error']}")
                    failed += 1
                else:
                    success += 1
                    logger.info(f"Triggered Kodi sync on {kodi.name}")
            except Exception as e:
                logger.error(f"Failed to sync Kodi {kodi.name} at {url}: {e}")
                failed += 1
                
    return {"success": success, "failed": failed}

