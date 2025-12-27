import asyncio
import logging
import time
import os
import sys
from typing import Callable, Optional
import aiohttp
from bot.config import config
from bot.telegram_utils import send_tg_alert
from bot.state import state_manager  # Глобальное состояние

async def _api_call(session: aiohttp.ClientSession, method: str, params: dict):
    """Внутренний API вызов"""
    url = f"https://api.telegram.org/bot{config.telegram_token}/{method}"
    async with session.get(url, params=params) as resp:
        return await resp.json()

async def telegram_control_loop(
    session: aiohttp.ClientSession,
    stop_cb: Callable[[], None],
    restart_cb: Callable[[], None]
):
    """
    ✅ КОМАНДЫ ТОЛЬКО ДЛЯ АДМИНОВ в ЛС бота!
    /status  – статус + очереди
    /stop    – graceful stop  
    /restart – полный перезапуск
    """
    if not config.telegram_token:
        logging.info("TG control disabled (no token)")
        return

    offset: Optional[int] = None
    logging.info("Telegram control loop started")
    await send_tg_alert(session, "🟢 <b>VkBotBuff</b> запущен! ✅")

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
                text = msg.get("text", "").strip().lower()

                # ✅ ТОЛЬКО ЛС БОТА + АДМИНЫ!
                if chat_id != int(config.telegram_chat_id or 0):
                    continue
                if from_id not in config.telegram_admin_ids:
                    await _api_call(session, "sendMessage", {
                        "chat_id": chat_id,
                        "text": "❌ Доступ запрещён! Только для админов.",
                    })
                    continue

                # ✅ КОМАНДЫ (ТОЛЬКО АДМИНЫ)
                if text == "/start":
                    await _api_call(session, "sendMessage", {
                        "chat_id": chat_id,
                        "text": (
                            "🤖 <b>VkBotBuff Control</b>\n\n"
                            "<b>Команды:</b>\n"
                            "• /status - статус бота\n"
                            "• /stop - остановить\n"
                            "• /restart - перезапуск\n\n"
                            "⚔️ Готов к работе!"
                        ),
                        "parse_mode": "HTML"
                    })

                elif text == "/status":
                    queue_info = []
                    for chat_id_num in list(state_manager.chat_states.keys()):
                        chat_state = state_manager.get_chat_state(chat_id_num)
                        queue_len = len(state_manager.request_queues.get(chat_id_num, []))
                        cd_left = max(0, config.cooldown - (time.time() - chat_state.last_buff_time))
                        queue_info.append(f"чат {chat_id_num}: CD={cd_left:.0f}s | очередь={queue_len}")
                    
                    status_text = (
                        "🟢 <b>VkBotBuff STATUS</b>\n\n"
                        f"🤖 ID: <code>{config.bot_id}</code>\n"
                        f"💬 Чаты: <code>{len(state_manager.chat_states)}</code>\n"
                        f"📊 <code>" + "\n".join(queue_info) + "</code>"
                    )
                    await _api_call(session, "sendMessage", {
                        "chat_id": chat_id,
                        "text": status_text,
                        "parse_mode": "HTML"
                    })

                elif text == "/stop":
                    await _api_call(session, "sendMessage", {
                        "chat_id": chat_id,
                        "text": "⛔ <b>Останавливаю VkBotBuff</b>…",
                        "parse_mode": "HTML"
                    })
                    await send_tg_alert(session, "🔴 VkBotBuff остановлен по команде /stop")
                    stop_cb()

                elif text == "/restart":
                    await _api_call(session, "sendMessage", {
                        "chat_id": chat_id,
                        "text": "♻️ <b>Перезапуск VkBotBuff</b>… (2 сек)",
                        "parse_mode": "HTML"
                    })
                    await send_tg_alert(session, "🔄 VkBotBuff <b>ПЕРЕЗАПУСК</b>…")
                    restart_cb()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"TG control error: {e}")
            await asyncio.sleep(5)

def restart_bot():
    """✅ ПОЛНЫЙ ПЕРЕЗАПУСК процесса"""
    print("[RESTART] Полный перезапуск бота...")
    logging.info("[RESTART] Полный перезапуск бота...")
    os.execv(sys.executable, [sys.executable, '-m', 'bot.main'])
