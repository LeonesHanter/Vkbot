import asyncio
import logging
import time
import aiohttp
from bot.config import config

_last_tg_error = ""
_last_tg_error_time = 0.0
_ERROR_REPEAT_WINDOW = 60

async def send_tg_alert(session: aiohttp.ClientSession, message: str):
    """✅ Уведомления + ошибки 1 раз в минуту!"""
    global _last_tg_error, _last_tg_error_time

    if not config.telegram_token or not config.telegram_chat_id:
        print(f"[TG] Нет токена/chat_id: {message[:50]}...")
        return False

    now = time.time()
    if message == _last_tg_error and now - _last_tg_error_time < _ERROR_REPEAT_WINDOW:
        return True

    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    params = {
        "chat_id": config.telegram_chat_id,
        "text": f"🤖 <b>BotBuff</b>\n\n{message}",
        "parse_mode": "HTML"
    }
    
    try:
        async with session.post(url, data=params, timeout=5) as resp:
            result = await resp.json()
            if result.get("ok"):
                _last_tg_error = message
                _last_tg_error_time = now
                print(f"[TG ALERT] ✅ {message[:50]}...")
                return True
            else:
                print(f"[TG ERROR] {result}")
                return False
    except Exception as e:
        print(f"[TG EXCEPTION] {e}")
        return False
