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

from .config import load_config
from .state import StateManager
from .handlers import ChatState

load_dotenv()

# Загрузка конфига и логирование
config = load_config()
logging.basicConfig(level=logging.INFO, filename=config.log_file, format='%(asctime)s - %(levelname)s - %(message)s')

# Telegram уведомления
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_tg_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram token or chat ID not set, skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {e}")

state_manager = StateManager()
# VK Bot с Long Poll
bot = Bot(token=config.token)

# Словарь для хранения состояний по чатам
chat_states = {}

# Regex для поиска "получено X золота"
GOLD_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
BLESSING_PATTERN = re.compile(r"благословение", re.IGNORECASE)

# ID последнего сообщения "Всех с новым годом" (хранится в памяти)
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
    peer_id = 2000000000 + chat_id  # Это будет source_chat_id (110)
    try:
        response = await bot_api.messages.send(
            peer_id=peer_id,
            message="Всех с новым годом",
            disable_mentions=1,
            random_id=time.time_ns() % 1000000000
        )
        last_new_year_message_id = response  # Сохраняем ID сообщения
        logging.info(f"Auto message sent to chat {chat_id}, ID: {last_new_year_message_id}")
    except Exception as e:
        logging.error(f"Failed to send auto message to chat {chat_id}: {e}")

async def schedule_new_year_messages():
    while True:
        await asyncio.sleep(10800)  # 3 часа
        for chat_id in chat_states:
            try:
                await send_new_year_message(bot.api, config.source_chat_id)  # Отправляем в source_chat_id
            except Exception as e:
                logging.error(f"Error in scheduling task for chat {config.source_chat_id}: {e}")

async def main():
    try:
        await init_chats()

        # Получаем ID бота (владельца токена)
        user_info = await bot.api.users.get()
        bot_id = user_info[0].id
        logging.info(f"Bot ID: {bot_id}")

        # Запускаем задачу с автоматическими сообщениями
        asyncio.create_task(schedule_new_year_messages())

        @bot.on.message()
        async def message_handler(message: Message):
            # Проверяем, является ли сообщение из "source" чата (110)
            if message.peer_id == (2000000000 + config.source_chat_id):
                text = message.text
                # Проверяем, содержит ли сообщение ID бота
                if str(bot_id) in text or f"id{bot_id}" in text:
                    # Ищем "получено X золота"
                    match = GOLD_PATTERN.search(text)
                    if match:
                        try:
                            gold_amount = int(match.group(1))
                            # Находим первый активный чат из config.chats
                            target_chat_id = None
                            for chat in config.chats:
                                if chat.enabled:
                                    target_chat_id = chat.chat_id
                                    break
                            if target_chat_id and target_chat_id in chat_states:
                                # Найти оригинальное сообщение, на которое было действие
                                # Попробуем найти сообщение, на которое оно ответило (reply_message)
                                original_user_message_id = None
                                if hasattr(message, 'reply_message') and message.reply_message:
                                    original_user_message_id = message.reply_message.id
                                # Если reply не доступен, используем forward
                                if not original_user_message_id and message.fwd_messages:
                                    # Берём первое пересланное сообщение как оригинальное
                                    original_user_message_id = message.fwd_messages[0].id
                                # Если не нашли оригинальное сообщение пользователя, выходим
                                if not original_user_message_id:
                                    logging.info(f"No original user message found for gold {gold_amount}, skipping.")
                                    return
                                # Если нашли, обрабатываем
                                await chat_states[target_chat_id].handle_gold_message(bot.api, gold_amount, original_user_message_id)
                        except ValueError:
                            pass

            # Проверяем, является ли сообщение из "target_user_id" (ЛС с сообществом)
            elif message.peer_id == config.target_user_id:
                text = message.text
                # Проверяем, отправлено ли сообщение от владельца токена
                if message.from_id == bot_id:
                    # Проверяем, содержит ли сообщение "благословение"
                    if BLESSING_PATTERN.search(text):
                        # Находим первый активный чат из config.chats
                        target_chat_id = None
                        for chat in config.chats:
                            if chat.enabled:
                                target_chat_id = chat.chat_id
                                break
                        if target_chat_id and target_chat_id in chat_states:
                            target_state = chat_states[target_chat_id]
                            # Обновляем время последнего благословения
                            target_state.update_last_bless_time()
                            logging.info(f"Manual blessing detected in user {config.target_user_id}, updating cooldown for chat {target_chat_id}.")

        def signal_handler():
            asyncio.create_task(shutdown())

        signal.signal(signal.SIGTERM, signal_handler)

        logging.info("BotBuff VK Bot started with Long Poll API")
        await bot.run_polling()
    except Exception as e:
        error_msg = f"❌ BotBuff VK Bot crashed: {e}"
        logging.error(error_msg)
        send_tg_alert(error_msg)
        raise

async def shutdown():
    logging.info("BotBuff VK Bot shutdown gracefully.")
    send_tg_alert("✅ BotBuff VK Bot stopped gracefully.")
    exit(0)

if __name__ == "__main__":
    asyncio.run(main())
