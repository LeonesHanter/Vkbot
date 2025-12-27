#!/usr/bin/env python3
import asyncio
import logging
import signal

import aiohttp

from bot.config import config
from bot.state import StateManager
from bot.handlers import (
    handle_command_message,
    handle_system_log,
    handle_manual_bless,
)
from bot.utils import get_long_poll_server, get_message, send_message
from bot.autopost import auto_post_loop
from bot.telegram_utils import send_tg_alert
from bot.telegram_bot import telegram_control_loop

logging.basicConfig(
    level=logging.INFO,
    filename=config.log_file,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

state_manager = StateManager(config)
state = state_manager.get_chat_state(config.main_chat_id)


async def shutdown():
    logging.info("BotBuff VK Bot shutdown gracefully.")
    send_tg_alert("✅ BotBuff VK Bot stopped gracefully.")
    raise SystemExit


def setup_signals():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(shutdown())
            )
        except NotImplementedError:
            pass


async def main():
    setup_signals()
    send_tg_alert("🚀 BotBuff VK Bot started.")

    async with aiohttp.ClientSession() as session:
        # автопост каждые 3 часа
        asyncio.create_task(auto_post_loop(session))

        # телеграм‑контроль (доступ только admin_ids)
        asyncio.create_task(
            telegram_control_loop(
                stop_cb=shutdown,
                restart_cb=shutdown,  # при желании можно изменить
            )
        )

        lp = await get_long_poll_server(session, config.token)
        server = lp["server"]
        key = lp["key"]
        ts = lp["ts"]

        logging.info(f"Long Poll server: {server}")

        while True:
            try:
                url = (
                    f"https://{server}?act=a_check&key={key}&ts={ts}"
                    "&wait=25&mode=2&version=3"
                )
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

                    await handle_command_message(msg, state)

                    await handle_system_log(
                        msg,
                        state,
                        lambda blessing, mid: send_message(
                            session,
                            config.token,
                            config.peer_id,
                            blessing,
                            mid,
                        ),
                    )

                    await handle_manual_bless(msg, state)

            except Exception as e:
                msg = f"Long Poll error: {e}"
                logging.error(msg)
                send_tg_alert(msg)
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
