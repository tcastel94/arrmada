"""Scraper service for creating Kodi NFOs and downloading artwork."""

import os
from pathlib import Path
from typing import Any, List
import httpx
import xml.etree.ElementTree as ET

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import async_session_factory
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
def map_path(p: str) -> str:
    if p.startswith("/media/"):
        return p.replace("/media/", "/mnt/user/medias/", 1)
    if p.startswith("/tv/"):
        return p.replace("/tv/", "/mnt/user/medias/seriesTV/", 1)
    if p.startswith("/data/"):
        return p.replace("/data/", "/mnt/user/downloads/", 1)
    return p
from app.utils.logger import get_logger

logger = get_logger(__name__)

async def scrape_movies(movies: List[dict]):
    """
    Scrape list of movies: generate NFOs and download posters/fanarts.
    movies = [{"movie_id": 1, "tmdb_id": 1234, "imdb_id": "tt123", "service_id": 1}]
    """
    # Create our own session since BackgroundTasks run after the route session closes
    async with async_session_factory() as db:
        # Group by service
        service_map = {}
        result = await db.execute(select(Service))
        for row in result.scalars().all():
            service_map[row.id] = row

    for m in movies:
        svc_name = m.get("source_service")
        svc = next((s for s in service_map.values() if s.name == svc_name), None)
        if not svc or svc.type != "radarr":
            svc = next((s for s in service_map.values() if s.type == "radarr"), None)
            
        if not svc:
            continue
            
        api_key = decrypt_api_key(svc.api_key)
        client = RadarrClient(url=svc.url, api_key=api_key)
        
        try:
            # 1. Fetch full metadata
            term = f"tmdb:{m['tmdb_id']}" if m.get("tmdb_id") else f"imdb:{m['imdb_id']}"
            if not m.get("tmdb_id") and not m.get("imdb_id"):
                continue
                
            results = await client.lookup_movie(term)
            if not results:
                continue
                
            movie_data = results[0]
            
            # If movie is already in radarr, we can get its path. 
            # Otherwise we skip (since we can't write NFO without a path).
            if not movie_data.get("path"):
                # try to get from db id
                if m.get("movie_id"):
                    try:
                        movie_data = await client.get_movie_by_id(m["movie_id"])
                    except Exception:
                        pass
            
            if not movie_data.get("path"):
                continue
                
            mapped_path = map_path(movie_data["path"])
            folder_path = Path(mapped_path)
            
            if not folder_path.exists():
                logger.error(f"Movie path does not exist: {folder_path}")
                continue

            # 2. Write NFO
            _write_nfo(folder_path, movie_data)
            
            # 3. Download artwork
            await _download_artwork(folder_path, movie_data)
            
        except Exception as e:
            logger.error(f"Error scraping movie {m}: {e}")
        finally:
            await client.close()


def _write_nfo(folder_path: Path, data: dict):
    root = ET.Element("movie")
    
    # Title
    ET.SubElement(root, "title").text = data.get("title", "")
    ET.SubElement(root, "originaltitle").text = data.get("originalTitle", "")
    ET.SubElement(root, "sorttitle").text = data.get("sortTitle", "")
    ET.SubElement(root, "year").text = str(data.get("year", ""))
    
    # Rating
    if "ratings" in data and "tmdb" in data["ratings"]:
        ET.SubElement(root, "rating").text = str(data["ratings"]["tmdb"].get("value", 0))
        ET.SubElement(root, "votes").text = str(data["ratings"]["tmdb"].get("votes", 0))
        
    ET.SubElement(root, "plot").text = data.get("overview", "")
    ET.SubElement(root, "runtime").text = str(data.get("runtime", 0))
    ET.SubElement(root, "mpaa").text = data.get("certification", "")
    ET.SubElement(root, "studio").text = data.get("studio", "")
    
    # IDs
    if data.get("tmdbId"):
        elem = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        elem.text = str(data["tmdbId"])
    if data.get("imdbId"):
        elem = ET.SubElement(root, "uniqueid", type="imdb")
        elem.text = str(data["imdbId"])

    # Genres
    for g in data.get("genres", []):
        ET.SubElement(root, "genre").text = g
        
    nfo_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode()
    
    # Find movie file name
    movie_file = data.get("movieFile")
    if movie_file and movie_file.get("relativePath"):
        nfo_name = Path(movie_file["relativePath"]).with_suffix(".nfo").name
    else:
        nfo_name = "movie.nfo"
        
    nfo_path = folder_path / nfo_name
    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write(nfo_str)
    logger.info(f"Written NFO at {nfo_path}")

async def _download_artwork(folder_path: Path, data: dict):
    async with httpx.AsyncClient(verify=False) as client:
        for img in data.get("images", []):
            try:
                url = img.get("remoteUrl")
                img_type = img.get("coverType") # poster or fanart
                if not url or not img_type: continue
                
                ext = url.split(".")[-1]
                if len(ext) > 4: ext = "jpg"
                
                filename = f"{img_type}.{ext}" if img_type in ["poster", "fanart", "background"] else f"img_{img_type}.{ext}"
                if img_type == "background": filename = f"fanart.{ext}"
                
                img_path = folder_path / filename
                if img_path.exists(): continue
                
                logger.info(f"Downloading artwork {url} to {img_path}")
                resp = await client.get(url, timeout=30.0)
                resp.raise_for_status()
                with open(img_path, "wb") as f:
                    f.write(resp.content)
            except Exception as e:
                logger.error(f"Failed to download artwork from {img.get('remoteUrl')}: {e}")
