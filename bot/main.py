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
        # Ошибка уже была отправлена, не отправляем снова
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            logging.error(f"Failed to send Telegram alert: {response.text}")
        else:
            # Обновляем последнюю ошибку
            last_tg_error = message
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

# bot_id будет обновляться при первом сообщении
bot_id = None

async def message_handler(message: Message):
    global bot_id
    if bot_id is None:
        # Устанавливаем bot_id при первом сообщении
        bot_id = message.from_id
        logging.info(f"Bot ID detected: {bot_id}")

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

async def main():
    try:
        await init_chats()

        # Запускаем задачу с автоматическими сообщениями
        asyncio.create_task(schedule_new_year_messages())

        # Регистрируем обработчик сообщений
        bot.on.message()(message_handler)

        def signal_handler():
            asyncio.create_task(shutdown())

        signal.signal(signal.SIGTERM, signal_handler)

        logging.info("BotBuff VK Bot started with Long Poll API")
        # Запускаем polling вручную
        await bot.api.messages.get_long_poll_server()
        while True:
            try:
                await bot.run_polling(skip_updates=True)
            except Exception as e:
                logging.error(f"Polling error: {e}")
                await asyncio.sleep(5)  # Ждём 5 секунд перед повтором
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
