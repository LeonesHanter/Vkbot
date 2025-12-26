import asyncio
import logging
import time
import os
import re
from dotenv import load_dotenv
import requests
from vkbottle import Bot

load_dotenv()

# 🔥 ФИКС: config ПЕРЕД импортами
class ChatConfig:
    def __init__(self, enabled=True, chat_id=110, cooldown=300, max_requests=5):
        self.enabled = enabled
        self.chat_id = chat_id
        self.cooldown = cooldown
        self.max_requests = max_requests

class BotConfig:
    def __init__(self):
        self.token = os.getenv("VK_USER_TOKEN", "")
        self.source_chat_id = 110
        self.target_user_id = 0
        self.log_file = "/home/FOK/vk-bots/Vkbot/bot.log"
        self.chats = [
            ChatConfig(chat_id=110, enabled=True, cooldown=300, max_requests=5),
        ]

def load_config():
    config = BotConfig()
    if not config.token:
        raise ValueError("❌ VK_USER_TOKEN не найден!")
    print(f"✅ Конфиг OK | Чат 110 | Токен: {config.token[:10]}...")
    return config

# Логирование
config = load_config()
logging.basicConfig(
    level=logging.INFO, 
    filename=config.log_file, 
    format='%(asctime)s - %(message)s',
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
        requests.post(url, data=data)
        last_tg_error = message
    except:
        pass

bot = Bot(token=config.token)
chat_states = {}
GOLD_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
bot_id = None

class SimpleChatState:
    def __init__(self, chat_id, cooldown, max_requests, **kwargs):
        self.chat_id = chat_id
        self.cooldown = cooldown
        self.max_requests = max_requests
        self.last_bless_time = 0
        self.request_count = 0
    
    async def handle_gold_message(self, api, gold_amount, message_id):
        peer_id = 2000000000 + self.chat_id
        try:
            await api.messages.send(
                peer_id=peer_id,
                message=f"💰 Баф за {gold_amount} золота! ✨",
                reply_to=message_id,
                random_id=int(time.time() * 1000)
            )
            logging.info(f"✅ Баф выдан в чат {self.chat_id}")
        except Exception as e:
            logging.error(f"Ошибка бафа: {e}")

async def init_chats():
    for chat_cfg in config.chats:
        if chat_cfg.enabled:
            chat_states[chat_cfg.chat_id] = SimpleChatState(
                chat_id=chat_cfg.chat_id,
                cooldown=chat_cfg.cooldown,
                max_requests=chat_cfg.max_requests
            )
    logging.info(f"✅ Чаты: {list(chat_states.keys())}")

async def message_handler(raw_message):
    global bot_id
    logging.info(f"📨 peer_id={raw_message.get('peer_id')}, text='{raw_message.get('text', '')[:50]}'")
    
    peer_id = raw_message.get('peer_id')
    from_id = raw_message.get('from_id')
    text = raw_message.get('text', '')
    
    if bot_id is None:
        bot_id = from_id
        logging.info(f"🤖 Bot ID: {bot_id}")

    chat_id = peer_id - 2000000000 if peer_id else 0
    
    if chat_id in chat_states:
        bot_id_str = str(bot_id)
        if bot_id_str in text or f"id{bot_id}" in text:
            match = GOLD_PATTERN.search(text)
            if match:
                gold_amount = int(match.group(1))
                logging.info(f"🪙 ЗОЛОТО {gold_amount} в чате {chat_id}")
                
                state = chat_states[chat_id]
                msg_id = raw_message.get('id', peer_id)
                
                await state.handle_gold_message(bot.api, gold_amount, msg_id)
                logging.info("✅ ✅ БАФ ВЫДАН!")

async def manual_polling():
    await init_chats()
    logging.info("🚀 BotBuff РАБОТАЕТ!")
    
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
                if update[0] == 4:  # message_new
                    await message_handler(update[1])  # RAW данные!
                    
        except Exception as e:
            logging.error(f"Long Poll: {str(e)[:100]}")
            await asyncio.sleep(3)

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(manual_polling())
    except KeyboardInterrupt:
        logging.info("🛑 Stop")
    finally:
        pass  # Без loop.close()

if __name__ == "__main__":
    asyncio.run(manual_polling())
else:
    run_bot()
