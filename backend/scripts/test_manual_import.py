"""Test get_stuck_downloads to see if Godfather items are filtered."""
import json
import asyncio
import sys
import logging
import io

sys.path.insert(0, ".")

log_buffer = io.StringIO()
handler = logging.StreamHandler(log_buffer)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(name)s | %(levelname)s | %(message)s"))
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)

from app.services.media_mover import get_stuck_downloads
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def test():
    engine = create_async_engine("sqlite+aiosqlite:///./data/arrmada.db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        stuck = await get_stuck_downloads(db)

    await engine.dispose()
    return stuck


result = asyncio.run(test())

with open("scripts/stuck_debug.log", "w", encoding="utf-8") as f:
    f.write("=== LOGS ===\n")
    f.write(log_buffer.getvalue())
    f.write("\n=== STUCK DOWNLOADS ===\n")
    f.write(f"Count: {len(result)}\n\n")
    for item in result:
        f.write(f"  {item['name']}\n")
        f.write(f"    category: {item['category']}\n")
        f.write(f"    storage:  {item['storage_path']}\n\n")

print(f"Done! {len(result)} stuck items")
for item in result:
    print(f"  {item['name']}")
