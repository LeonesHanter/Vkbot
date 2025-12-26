import asyncio
import logging
import signal
import time
import os
import re
from dotenv import load_dotenv
import requests
from vkbottle import Bot
from vkbottle.bot import Message

from bot.config import load_config
from bot.state import StateManager
from bot.handlers import ChatState

load_dotenv()

# Загрузка конфига и логирование
config = load_config()
logging.basicConfig(level=logging.INFO, filename=config.log_file, format='%(asctime)s - %(levelname)s - %(message)s')

# Telegram уведомления
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Хранение последней ошибки
last_tg_error = ""

def send_tg_alert(message):
    global last_tg_error
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram token or chat ID not set, skipping alert.")
        return
    if message == last_tg_error:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            logging.error(f"Failed to send Telegram alert: {response.text}")
        else:
            last_tg_error = message
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {e}")

state_manager = StateManager()
bot = Bot(token=config.token)
chat_states = {}

GOLD_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
BLESSING_PATTERN = re.compile(r"благословение", re.IGNORECASE)
last_new_year_message_id = 0

async def init_chats():
    for chat_cfg in config.chats:
        if chat_cfg.enabled:
            chat_states[chat_cfg.chat_id] = ChatState(
                chat_id=chat_cfg.chat_id,
                cooldown=chat_cfg.cooldown,
                max_requests=chat_cfg.max_requests,
                state_manager=state_manager,
                target_user_id=config.target_user_id
            )

async def send_new_year_message(bot_api, chat_id: int):
    global last_new_year_message_id
    peer_id = 2000000000 + chat_id
    try:
        response = await bot_api.messages.send(
            peer_id=peer_id,
            message="Всех с новым годом",
            disable_mentions=1,
            random_id=time.time_ns() % 1000000000
        )
        last_new_year_message_id = response
        logging.info(f"Auto message sent to chat {chat_id}, ID: {last_new_year_message_id}")
    except Exception as e:
        logging.error(f"Failed to send auto message to chat {chat_id}: {e}")

async def schedule_new_year_messages():
    while True:
        await asyncio.sleep(10800)  # 3 часа
        try:
            await send_new_year_message(bot.api, config.source_chat_id)
        except Exception as e:
            logging.error(f"Error in scheduling task: {e}")

bot_id = None

@bot.on.message()
async def message_handler(message: Message):
    global bot_id
    if bot_id is None:
        bot_id = message.from_id
        logging.info(f"Bot ID detected: {bot_id}")

    if message.peer_id == (2000000000 + config.source_chat_id):
        text = message.text
        if str(bot_id) in text or f"id{bot_id}" in text:
            match = GOLD_PATTERN.search(text)
            if match:
                try:
                    gold_amount = int(match.group(1))
                    target_chat_id = None
                    for chat in config.chats:
                        if chat.enabled:
                            target_chat_id = chat.chat_id
                            break
                    if target_chat_id and target_chat_id in chat_states:
                        original_user_message_id = None
                        if message.reply_message:
                            original_user_message_id = message.reply_message.id
                        elif message.fwd_messages:
                            original_user_message_id = message.fwd_messages[0].id
                        if not original_user_message_id:
                            logging.info(f"No original user message found for gold {gold_amount}, skipping.")
                            return
                        await chat_states[target_chat_id].handle_gold_message(bot.api, gold_amount, original_user_message_id)
                except ValueError:
                    pass

    elif message.peer_id == config.target_user_id:
        text = message.text
        if message.from_id == bot_id:
            if BLESSING_PATTERN.search(text):
                target_chat_id = None
                for chat in config.chats:
                    if chat.enabled:
                        target_chat_id = chat.chat_id
                        break
                if target_chat_id and target_chat_id in chat_states:
                    target_state = chat_states[target_chat_id]
                    target_state.update_last_bless_time()
                    logging.info(f"Manual blessing detected in user {config.target_user_id}, updating cooldown for chat {target_chat_id}.")

async def main():
    try:
        await init_chats()
        asyncio.create_task(schedule_new_year_messages())
        logging.info("BotBuff VK Bot started with Long Poll API")
        await bot.run_polling()
    except KeyboardInterrupt:
        logging.info("BotBuff VK Bot stopped by user.")
        send_tg_alert("🛑 BotBuff VK Bot stopped by user.")
    except Exception as e:
        error_msg = f"❌ BotBuff VK Bot crashed: {e}"
        logging.error(error_msg)
        send_tg_alert(error_msg)
        raise

def run_bot():
    """КРИТИЧЕСКИ ВАЖНО для systemd - создаёт свой event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("SIGINT received")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        send_tg_alert(f"❌ BotBuff VK Bot fatal error: {e}")
    finally:
        # Graceful shutdown
        tasks = [task for task in asyncio.all_tasks(loop) if task is not asyncio.current_task(loop)]
        for task in tasks:
            task.cancel()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == "__main__":
    # Локальный запуск
    asyncio.run(main())
else:
    # systemd запуск
    run_bot()
