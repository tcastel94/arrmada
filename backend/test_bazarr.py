import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.api.subtitles import _get_bazarr

async def main():
    engine = create_async_engine("postgresql+asyncpg://arrmada:arrmada@localhost:5432/arrmada")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        bazarr = await _get_bazarr(db)
        print("Bazarr client:", bazarr)
        try:
            print("Movies:", await bazarr.get_movies(length=1))
        except Exception as e:
            print("Error getting movies:", e)
        finally:
            await bazarr.close()

if __name__ == "__main__":
    asyncio.run(main())
