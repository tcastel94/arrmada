"""Test Telegram notification."""
import asyncio
from app.services.telegram import send_message

async def main():
    result = await send_message(
        "🏴\u200d☠️ <b>ArrMada</b> est en ligne !\n"
        "Tous vos services sont connectés et opérationnels.\n\n"
        "🎬 <b>Films:</b> 257 | 📺 <b>Séries:</b> 33 | 💾 <b>7.0 TB</b>"
    )
    print(f"Telegram sent: {result}")

asyncio.run(main())
