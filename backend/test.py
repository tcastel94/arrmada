import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.service import Service
from app.services.encryption import decrypt_api_key
import httpx

async def main():
    engine = create_async_engine('postgresql+asyncpg://arrmada:arrmada@arrmada-db:5432/arrmada')
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        stmt = select(Service).where(Service.type == 'bazarr')
        result = await db.execute(stmt)
        svc = result.scalars().first()
        url = svc.url
        api_key = decrypt_api_key(svc.api_key)
        
        async with httpx.AsyncClient() as client:
            try:
                print('Testing GET status')
                r = await client.get(f'{url}/api/system/status', headers={'X-API-KEY': api_key}, timeout=5.0)
                print('Status:', r.status_code)
                
                print('Testing query param POST')
                params = {
                    'radarrid': '1',
                    'subtitle': 'test',
                    'provider': 'test',
                    'original_format': '',
                    'hi': 'False',
                    'forced': 'False'
                }
                # we don't care if it fails, just if it rejects the method/format quickly (like 400 Bad Request vs 404 or hanging)
                r2 = await client.post(f'{url}/api/providers/movies', params=params, headers={'X-API-KEY': api_key}, timeout=5.0)
                print('Query POST Status:', r2.status_code)
                print('Query POST Text:', r2.text)
                
            except Exception as e:
                print('Error:', e)
            
            try:
                print('Testing json body POST')
                r3 = await client.post(f'{url}/api/providers/movies', json=params, headers={'X-API-KEY': api_key}, timeout=5.0)
                print('JSON POST Status:', r3.status_code)
                print('JSON POST Text:', r3.text)
            except Exception as e:
                print('Error:', e)
            
if __name__ == '__main__':
    asyncio.run(main())
