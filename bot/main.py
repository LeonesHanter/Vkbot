import asyncio
import logging
import time
import aiohttp
import sys
import os

from bot.config import config
from bot.state import StateManager
from bot.handlers import handle_all_messages
from bot.utils import get_long_poll_server, get_message
from bot.autopost import auto_post_loop
from bot.telegram_utils import send_tg_alert
from bot.telegram_bot import telegram_control_loop, restart_bot

logging.basicConfig(
    level=logging.INFO,
    filename=config.log_file,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

state_manager = StateManager(config)
global_state_manager = state_manager

async def process_queue_loop():
    """✅ Тихая очередь + cleanup каждые 5s"""
    while True:
        try:
            cleaned = global_state_manager.cleanup_expired_pending()
            if cleaned:
                print(f"[CLEANUP] Удалено {cleaned} просроченных pending")

            now = time.time()
            for chat_id in list(state_manager.chat_states.keys()):
                chat_state = state_manager.get_chat_state(chat_id)
                queue_len = len(state_manager.request_queues.get(chat_id, []))
                cd_left = max(0, config.cooldown - (now - chat_state.last_buff_time))
                
                if queue_len > 0 or cd_left == 0:
                    print(f"[QUEUE] чат {chat_id}: CD={cd_left:.0f}s | очередь={queue_len}")
                
                if cd_left == 0 and queue_len > 0:
                    print(f"[QUEUE AUTO] ✅ Активируем чат {chat_id}")
                    state_manager.process_next_in_queue(chat_id)

            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"[QUEUE LOOP] {e}")
            await asyncio.sleep(5)

async def graceful_shutdown():
    """Graceful остановка"""
    print("[SHUTDOWN] Graceful остановка...")
    sys.exit(0)

async def main():
    print(f"[CONFIG] Bot ID определён: {config.bot_id} (receiver_id: {config.receiver_id})")
    print("[STATE] Инициализация состояний...")

    async with aiohttp.ClientSession() as session:
        # ✅ 4 ПАРАЛЛЕЛЬНЫХ ЦИКЛА
        queue_task = asyncio.create_task(process_queue_loop())
        autopost_task = asyncio.create_task(auto_post_loop(session))
        telegram_task = asyncio.create_task(
            telegram_control_loop(
                session=session,
                stop_cb=graceful_shutdown,
                restart_cb=restart_bot  # ✅ ПОЛНЫЙ ПЕРЕЗАПУСК!
            )
        )

        # LongPoll VK
        lp = await get_long_poll_server(session, config.token)
        server = lp["server"]
        key = lp["key"]
        ts = lp["ts"]

        await send_tg_alert(session, "🚀 <b>VkBotBuff</b> полностью готов! ✅")
        print(f"[LP] LongPoll подключён: {server}")
        print("[BOT] ✅ Готов к работе! (ТГ: /status /stop /restart)")

        while True:
            try:
                url = f"https://{server}?act=a_check&key={key}&ts={ts}&wait=25&mode=2&version=3"
                async with session.get(url) as resp:
                    data = await resp.json()
                ts = data["ts"]

                for update in data.get("updates", []):
                    if update[0] != 4:
                        continue

                    payload = update[1]
                    if isinstance(payload, int):
                        msg = await get_message(session, config.token, payload)
                        if not msg:
                            continue
                    else:
                        msg = payload

                    await handle_all_messages(msg, global_state_manager)

            except Exception as e:
                error_msg = f"[LP ERROR] {e}"
                print(error_msg)
                await send_tg_alert(session, f"⚠️ {error_msg}")

if __name__ == "__main__":
    asyncio.run(main())
