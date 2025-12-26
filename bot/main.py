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

config = load_config()
logging.basicConfig(level=logging.INFO, filename=config.log_file, format='%(asctime)s - %(levelname)s - %(message)s')

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
last_tg_error = ""

def send_tg_alert(message):
    global last_tg_error
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or message == last_tg_error:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            last_tg_error = message
    except Exception as e:
        logging.error(f"Failed to send Telegram alert: {e}")

state_manager = StateManager()
bot = Bot(token=config.token)
chat_states = {}
GOLD_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
BLESSING_PATTERN = re.compile(r"благословение", re.IGNORECASE)
last_new_year_message_id = 0
bot_id = None

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
    logging.info(f"Инициализировано чатов: {len(chat_states)}")

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
        await asyncio.sleep(10800)
        try:
            await send_new_year_message(bot.api, config.source_chat_id)
        except Exception as e:
            logging.error(f"Error in scheduling task: {e}")

@bot.on.message()
async def message_handler(message: Message):
    global bot_id
    
    # 🚨 ОТЛАДКА
    logging.info(f"📨 peer_id={message.peer_id}, from_id={message.from_id}, text='{message.text[:100]}'")
    
    if bot_id is None:
        bot_id = message.from_id
        logging.info(f"🤖 Bot ID detected: {bot_id}")

    # 🎯 НОВАЯ ЛОГИКА: баф в ТОМ ЖЕ чате где золото!
    chat_id = message.peer_id - 2000000000  # Извлекаем chat_id из peer_id
    
    logging.info(f"🔍 Chat ID: {chat_id}, source_chat_id: {config.source_chat_id}")
    
    # Проверяем ВСЕ чаты (включая source_chat)
    if chat_id in chat_states:
        logging.info("✅ Сообщение из отслеживаемого чата!")
        text = message.text or ""
        
        # Проверяем упоминание бота
        bot_id_str = str(bot_id)
        has_bot_id = bot_id_str in text or f"id{bot_id}" in text
        logging.info(f"🤖 Bot ID '{bot_id_str}' в тексте: {has_bot_id}")
        
        if has_bot_id:
            match = GOLD_PATTERN.search(text)
            logging.info(f"💰 GOLD_PATTERN: {match}")
            
            if match:
                try:
                    gold_amount = int(match.group(1))
                    logging.info(f"🪙 НАЙДЕНО ЗОЛОТО: {gold_amount}")
                    
                    state = chat_states[chat_id]
                    logging.info(f"📊 State для чата {chat_id}: cooldown={state.cooldown}, requests={state.max_requests}")
                    
                    # 🔥 ВЫДАЁМ БАФ В ТОМ ЖЕ ЧАТЕ!
                    logging.info(f"🚀 Вызываем handle_gold_message в чате {chat_id}")
                    await state.handle_gold_message(bot.api, gold_amount, message.id)  # Используем ID текущего сообщения!
                    logging.info("✅ Баф выдан в том же чате!")
                    
                except ValueError as e:
                    logging.error(f"❌ ValueError парсинга золота: {e}")
            else:
                logging.info("❌ GOLD_PATTERN не найден")
        else:
            logging.info("❌ Bot ID не найден в тексте")
    elif message.peer_id == config.target_user_id:
        # ЛС благословение (остаётся для обратной совместимости)
        logging.info(f"💫 ЛС target_user_id: {message.text[:50]}")
        if message.from_id == bot_id and BLESSING_PATTERN.search(message.text or ""):
            for chat_id, state in chat_states.items():
                state.update_last_bless_time()
                logging.info(f"🙏 Manual blessing обновлен для чата {chat_id}")

async def manual_polling():
    await init_chats()
    asyncio.create_task(schedule_new_year_messages())
    logging.info("✅ BotBuff VK Bot started - БАФ В ТОМ ЖЕ ЧАТЕ!")
    
    server_info = await bot.api.messages.get_long_poll_server()
    server_url = f"https://{server_info.server}"
    key = server_info.key
    ts = server_info.ts
    
    while True:
        try:
            response = await bot.api.http_client.request_json(
                f"{server_url}?act=a_check&key={key}&ts={ts}&wait=25&mode=2"
            )
            ts = response["ts"]
            for update in response["updates"]:
                if update[0] == 4:  # message_new
                    message = Message(**update[1])
                    await message_handler(message)
        except Exception as e:
            logging.error(f"Long Poll error: {e}")
            await asyncio.sleep(5)

def run_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manual_polling())
    except KeyboardInterrupt:
        logging.info("Bot stopped by SIGINT")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        send_tg_alert(f"❌ BotBuff VK Bot fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(manual_polling())
else:
    run_bot()
