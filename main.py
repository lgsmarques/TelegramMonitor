import os
import asyncio
import time
import logging

import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# --- Config -----------------------------------------------------------

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["TELEGRAM_SESSION_STRING"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

KEYWORDS: list[str] = [
    kw.strip().lower()
    for kw in os.environ.get("KEYWORDS", "").split(",")
    if kw.strip()
]

# Opcional: só monitorar esses canais (username ou id). Vazio = todos.
CHANNEL_FILTER: set[str] = {
    c.strip().lstrip("@").lower()
    for c in os.environ.get("TELEGRAM_CHANNELS", "").split(",")
    if c.strip()
}

COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "60"))

# cooldown_cache[(channel_id, keyword)] = monotonic timestamp do último alerta
_cooldown: dict[tuple[str, str], float] = {}

# -----------------------------------------------------------------------


def matched_keywords(text: str) -> list[str]:
    lower = text.lower()
    return [kw for kw in KEYWORDS if kw in lower]


def on_cooldown(channel_id: str, keyword: str) -> bool:
    key = (channel_id, keyword)
    return time.monotonic() - _cooldown.get(key, 0) < COOLDOWN_SECONDS


def mark_sent(channel_id: str, keyword: str) -> None:
    _cooldown[(channel_id, keyword)] = time.monotonic()


async def send_discord_alert(
    channel_name: str,
    channel_username: str | None,
    message_id: int,
    text: str,
    matched: list[str],
) -> None:
    log.info("Sending alert to Discord for [%s] keywords=%s", channel_name, matched)
    
    link = (
        f"https://t.me/{channel_username}/{message_id}"
        if channel_username
        else "_(canal privado — sem link público)_"
    )

    embed = {
        "title": f"\U0001f6d2 Promoção em {channel_name}",
        "description": text[:2000],
        "color": 0x2BBBAD,
        "fields": [
            {
                "name": "Keywords",
                "value": " ".join(f"`{kw}`" for kw in matched),
                "inline": True,
            },
            {"name": "Link", "value": link, "inline": False},
        ],
        "footer": {"text": "Telegram Monitor"},
    }

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        resp.raise_for_status()
        log.info("Alerta enviado: [%s] keywords=%s", channel_name, matched)


client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


@client.on(events.NewMessage())
async def handler(event: events.NewMessage.Event) -> None:
    log.info("Handling new message...")
    if not event.is_channel:
        return

    text = event.message.text or ""
    if not text:
        return
    
    log.info("Message text: %s", text[:100].replace("\n", " "))

    chat = await event.get_chat()
    channel_id = str(chat.id)
    channel_name: str = getattr(chat, "title", channel_id)
    channel_username: str | None = getattr(chat, "username", None) or None

    if CHANNEL_FILTER:
        identifiers = {channel_id}
        if channel_username:
            identifiers.add(channel_username.lower())
        if identifiers.isdisjoint(CHANNEL_FILTER):
            return

    hits = matched_keywords(text)
    if not hits:
        return

    # Filtra keywords em cooldown e registra as que vão ser enviadas
    new_hits = [kw for kw in hits if not on_cooldown(channel_id, kw)]
    if not new_hits:
        log.debug("Cooldown ativo para [%s] keywords=%s", channel_name, hits)
        return

    for kw in new_hits:
        mark_sent(channel_id, kw)

    await send_discord_alert(
        channel_name, channel_username, event.message.id, text, new_hits
    )


async def main() -> None:
    log.info("Iniciando...")
    if not KEYWORDS:
        log.warning("Nenhuma keyword em KEYWORDS — todos os canais serão monitorados sem filtro.")
    if CHANNEL_FILTER:
        log.info("Filtrando canais: %s", CHANNEL_FILTER)

    await client.start()
    log.info("Conectado ao Telegram. Monitorando mensagens...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
