import asyncio
import logging
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
logging.basicConfig(
    level=logging.INFO, 
    filename=config.log_file, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

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
        logging.error(f"Telegram alert failed: {e}")

state_manager = StateManager()
bot = Bot(token=config.token)
chat_states = {}
GOLD_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
BLESSING_PATTERN = re.compile(r"благословение", re.IGNORECASE)
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
    logging.info(f"✅ Инициализировано чатов: {len(chat_states)}")

@bot.on.message()
async def message_handler(message: Message):
    global bot_id
    
    logging.info(f"📨 peer_id={message.peer_id}, from_id={message.from_id}, text='{message.text[:100]}'")
    
    if bot_id is None:
        bot_id = message.from_id
        logging.info(f"🤖 Bot ID определён: {bot_id}")

    # 🔥 НОВАЯ ЛОГИКА: баф в том же чате!
    chat_id = message.peer_id - 2000000000
    
    if chat_id in chat_states:
        logging.info(f"✅ Чат {chat_id} отслеживается!")
        text = message.text or ""
        
        bot_id_str = str(bot_id)
        has_bot_id = bot_id_str in text or f"id{bot_id}" in text
        logging.info(f"🤖 Bot ID в тексте: {has_bot_id}")
        
        if has_bot_id:
            match = GOLD_PATTERN.search(text)
            if match:
                gold_amount = int(match.group(1))
                logging.info(f"🪙 НАЙДЕНО ЗОЛОТО: {gold_amount}")
                
                state = chat_states[chat_id]
                original_msg_id = message.id  # Текущее сообщение
                
                logging.info(f"🚀 Баф в чате {chat_id}, msg_id={original_msg_id}")
                await state.handle_gold_message(bot.api, gold_amount, original_msg_id)
                logging.info("✅ ✅ БАФ ВЫДАН В ТОМ ЖЕ ЧАТЕ!")
            else:
                logging.info("❌ Нет 'получено X золота'")
    else:
        logging.debug(f"📍 Чат {chat_id} не отслеживается")

async def manual_polling():
    """🔧 ИСПРАВЛЕННЫЙ Long Poll парсинг"""
    await init_chats()
    asyncio.create_task(send_periodic_messages())
    logging.info("🚀 BotBuff запущен - БАФ В ТОМ ЖЕ ЧАТЕ!")
    
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
            
            for update in response.get("updates", []):
                try:
                    # 🔥 ИСПРАВЛЕНИЕ: правильный парсинг message_new
                    if update[0] == 4:  # message_new
                        message_obj = update[1]
                        if isinstance(message_obj, dict):
                            message = Message(**message_obj)
                            await message_handler(message)
                        else:
                            logging.debug(f"⏭️ Пропуск не-dict сообщения: {type(message_obj)}")
                except Exception as e:
                    logging.error(f"Ошибка обработки update {update[:2]}: {e}")
                    
        except Exception as e:
            logging.error(f"Long Poll ошибка: {e}")
            await asyncio.sleep(5)

async def send_periodic_messages():
    """Авто-сообщения каждые 3 часа"""
    while True:
        await asyncio.sleep(10800)  # 3 часа
        peer_id = 2000000000 + config.source_chat_id
        try:
            await bot.api.messages.send(
                peer_id=peer_id,
                message="Всех с новым годом! 🎄",
                disable_mentions=1,
                random_id=int(time.time() * 1000)
            )
            logging.info(f"🎄 Авто-сообщение в чат {config.source_chat_id}")
        except Exception as e:
            logging.error(f"Ошибка авто-сообщения: {e}")

def run_bot():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manual_polling())
    except KeyboardInterrupt:
        logging.info("🛑 Остановка по SIGINT")
    except Exception as e:
        logging.error(f"💥 Критическая ошибка: {e}")
        send_tg_alert(f"💥 BotBuff упал: {e}")

if __name__ == "__main__":
    asyncio.run(manual_polling())
else:
    run_bot()
