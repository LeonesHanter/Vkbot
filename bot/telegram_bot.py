import asyncio
import logging
from typing import Optional

import aiohttp

from .config import config
from .telegram_utils import send_tg_alert


async def _api_call(session: aiohttp.ClientSession, method: str, params: dict):
    url = f"https://api.telegram.org/bot{config.telegram_token}/{method}"
    async with session.get(url, params=params) as resp:
        return await resp.json()


async def telegram_control_loop(stop_cb, restart_cb):
    """
    /status  – статус
    /stop    – стоп
    /restart – сейчас такая же логика как stop_cb
    Доступ только admin_ids и только в TELEGRAM_CHAT_ID.
    """
    if not config.telegram_token or not config.telegram_chat_id:
        logging.info("TG control disabled (no token/chat id)")
        return

    offset: Optional[int] = None
    logging.info("Telegram control loop started")
    send_tg_alert("🟢 Telegram control loop started")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                params = {"timeout": 25}
                if offset is not None:
                    params["offset"] = offset
                data = await _api_call(session, "getUpdates", params)

                if not data.get("ok"):
                    logging.error(f"TG getUpdates error: {data}")
                    await asyncio.sleep(5)
                    continue

                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1

                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        continue

                    chat_id = msg["chat"]["id"]
                    from_id = msg["from"]["id"]
                    text = msg.get("text", "")

                    if chat_id != int(config.telegram_chat_id):
                        continue
                    if from_id not in config.telegram_admin_ids:
                        continue

                    cmd = text.strip().lower()
                    if cmd == "/status":
                        await _api_call(
                            session,
                            "sendMessage",
                            {
                                "chat_id": chat_id,
                                "text": "Vkbot: работаю ✅",
                            },
                        )
                    elif cmd == "/stop":
                        await _api_call(
                            session,
                            "sendMessage",
                            {
                                "chat_id": chat_id,
                                "text": "Останавливаю Vkbot… ⛔",
                            },
                        )
                        await stop_cb()
                    elif cmd == "/restart":
                        await _api_call(
                            session,
                            "sendMessage",
                            {
                                "chat_id": chat_id,
                                "text": "Перезапуск Vkbot… ♻️",
                            },
                        )
                        await restart_cb()

            except Exception as e:
                logging.error(f"TG control error: {e}")
                await asyncio.sleep(5)


