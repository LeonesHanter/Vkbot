import asyncio
import time
import os
import sys
from typing import Callable, Optional
import aiohttp
from bot.config import config
from bot.telegram_utils import send_tg_alert

state_manager = None
_last_processed_update = None

async def _api_call(session: aiohttp.ClientSession, method: str, params: dict):
    url = f"https://api.telegram.org/bot{config.telegram_token}/{method}"
    async with session.post(url, json=params, timeout=10) as resp:
        return await resp.json()

async def telegram_control_loop(session, stop_cb, restart_cb, _state_manager):
    global state_manager, _last_processed_update
    state_manager = _state_manager

    print("🚀 [TG] Telegram control loop STARTED")
    await send_tg_alert(session, "🟢 Telegram control READY")

    cleanup_data = await _api_call(session, "getUpdates", {"offset": -1, "limit": 1})
    if cleanup_data.get("result"):
        _last_processed_update = cleanup_data["result"][-1]["update_id"] + 1
        print(f"🧹 [TG] Кеш очищен, offset={_last_processed_update}")

    while True:
        try:
            params = {"timeout": 25}
            if _last_processed_update:
                params["offset"] = _last_processed_update

            data = await _api_call(session, "getUpdates", params)
            if not data.get("ok"):
                print(f"[TG] ❌ getUpdates error")
                await asyncio.sleep(5)
                continue

            updates = data.get("result", [])
            if not updates:
                await asyncio.sleep(2)
                continue

            for upd in updates:
                _last_processed_update = upd["update_id"] + 1
                
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                from_id = msg["from"]["id"]
                text = (msg.get("text") or "").strip().lower()

                print(f"🔥 [TG LIVE] chat={chat_id} from={from_id} text='{text}'")

                if str(chat_id) != str(config.telegram_chat_id):
                    continue

                if from_id not in config.telegram_admin_ids:
                    print(f"❌ [TG] Не админ {from_id}")
                    continue

                print(f"✅ [TG] АДМИН {from_id} → '{text}'")

                response = f"✅ <b>BotBuff LIVE</b>\nКоманда: <code>{text}</code>"
                
                if text == "/status":
                    response += f"\nЧаты: {len(state_manager.chat_states) if state_manager else 0}"
                elif text == "/stop":
                    stop_cb()
                    return
                elif text == "/restart":
                    restart_cb()
                    return

                await _api_call(session, "sendMessage", {
                    "chat_id": chat_id,
                    "text": response,
                    "parse_mode": "HTML"
                })
                print(f"✅ [TG] ОТВЕТ: {text}")

        except Exception as e:
            print(f"💥 [TG ERROR] {e}")
            await asyncio.sleep(5)

def restart_bot():
    print("♻️ [RESTART] Полный перезапуск!")
    os.execv(sys.executable, [sys.executable, '-m', 'bot.main'])
