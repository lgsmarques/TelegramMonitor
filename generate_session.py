"""
Execute este script UMA VEZ localmente para gerar o TELEGRAM_SESSION_STRING.
Salve a string gerada como variável de ambiente no Railway.

Uso:
    pip install telethon
    python generate_session.py
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("\n=== TELEGRAM_SESSION_STRING ===")
        print(client.session.save())
        print("================================")
        print("\nCopie a string acima e salve como TELEGRAM_SESSION_STRING no Railway.")


if __name__ == "__main__":
    asyncio.run(main())
