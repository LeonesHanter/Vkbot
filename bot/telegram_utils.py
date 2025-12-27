import asyncio
import logging
import time
from typing import Optional
import aiohttp
from bot.config import config

_last_tg_error = ""
_last_tg_error_time = 0.0
_ERROR_REPEAT_WINDOW = 60  # сек

async def send_tg_alert(session: aiohttp.ClientSession, message: str):
    """✅ Алерты В САМ БОТ (никому не спамит!)"""
    global _last_tg_error, _last_tg_error_time

    if not config.telegram_token:
        logging.warning("Telegram token не задан, алерт пропущен")
        return False

    now = time.time()
    if message == _last_tg_error and now - _last_tg_error_time < _ERROR_REPEAT_WINDOW:
        return True

    # ✅ ЛС БОТА (никому не отправляем!)
    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    params = {
        "chat_id": config.telegram_chat_id or "BOT_SELF",  # ЛС бота
        "text": f"🤖 <b>VK BotBuff</b>\n\n{message}",
        "parse_mode": "HTML"
    }
    
    try:
        async with session.post(url, data=params, timeout=5) as resp:
            if resp.status == 200:
                _last_tg_error = message
                _last_tg_error_time = now
                print(f"[TG] ✅ Алерт отправлен в бота")
                return True
            else:
                logging.error(f"TG alert failed: {await resp.text()}")
                return False
    except Exception as e:
        logging.error(f"TG alert exception: {e}")
        return False
