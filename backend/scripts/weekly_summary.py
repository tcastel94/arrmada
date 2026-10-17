import asyncio
import sys
from sqlalchemy import select
from datetime import datetime, timedelta
from app.database import async_session_factory
from app.models.service import Service
from app.services.telegram import send_message
from app.services.ai_assistant import generate_weekly_summary
from app.services.encryption import decrypt_api_key
import httpx

async def get_recent_additions(client: httpx.AsyncClient, service_type: str) -> list[str]:
    """Fetch history from Sonarr/Radarr for the past 7 days."""
    try:
        # Sonarr/Radarr history API
        if service_type == "radarr":
            resp = await client.get("/api/v3/movie")
            movies = resp.json()
            # Filter movies added in last 7 days
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent = []
            for m in movies:
                added = m.get("added")
                if added:
                    # Parse 2026-08-27T10:10:10Z
                    try:
                        added_dt = datetime.strptime(added[:19], "%Y-%m-%dT%H:%M:%S")
                        if added_dt > week_ago:
                            recent.append(m.get("title", ""))
                    except:
                        pass
            return recent
        
        elif service_type == "sonarr":
            resp = await client.get("/api/v3/series")
            series = resp.json()
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent = []
            for s in series:
                added = s.get("added")
                if added:
                    try:
                        added_dt = datetime.strptime(added[:19], "%Y-%m-%dT%H:%M:%S")
                        if added_dt > week_ago:
                            recent.append(s.get("title", ""))
                    except:
                        pass
            return recent
    except Exception as e:
        print(f"Error fetching history for {service_type}: {e}")
        return []
    return []

async def main():
    async with async_session_factory() as session:
        radarr = (await session.execute(select(Service).where(Service.type == "radarr", Service.is_enabled == True))).scalars().first()
        sonarr = (await session.execute(select(Service).where(Service.type == "sonarr", Service.is_enabled == True))).scalars().first()
        
        recent_movies = []
        recent_shows = []
        
        if radarr:
            headers = {"X-Api-Key": decrypt_api_key(radarr.api_key)}
            async with httpx.AsyncClient(base_url=radarr.url, headers=headers) as client:
                recent_movies = await get_recent_additions(client, "radarr")
                
        if sonarr:
            headers = {"X-Api-Key": decrypt_api_key(sonarr.api_key)}
            async with httpx.AsyncClient(base_url=sonarr.url, headers=headers) as client:
                recent_shows = await get_recent_additions(client, "sonarr")
                
        summary_msg = await generate_weekly_summary(recent_movies, recent_shows)
        
        print("Envoi du bilan hebdo via Telegram...")
        success = await send_message(summary_msg)
        if success:
            print("Bilan envoyé avec succès.")
        else:
            print("Erreur lors de l'envoi du bilan.")

if __name__ == "__main__":
    asyncio.run(main())
