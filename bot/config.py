import asyncio
import logging
import os
from dotenv import load_dotenv
from vkbottle import Bot

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
print("🚀 START")

class BotConfig:
    token = os.getenv("VK_USER_TOKEN")
    chats = [110]

config = BotConfig()
if not config.token:
    print("❌ NO TOKEN")
    exit(1)

print(f"✅ TOKEN OK: {config.token[:10]}...")
bot = Bot(token=config.token)

chat_states = {110: {"chat_id": 110}}

async def handler(raw_message):
    print(f"📨 MESSAGE: {raw_message}")
    peer_id = raw_message.get('peer_id')
    text = raw_message.get('text', '')
    
    if peer_id == 2000000110 and 'получено' in text:
        print(f"🪙 GOLD FOUND: {text}")
        await bot.api.messages.send(
            peer_id=peer_id,
            message="💰 БАФ ЗА ЗОЛОТО!",
            random_id=0
        )
        print("✅ БАФ ОТПРАВЛЕН!")

async def poll():
    print("🔄 Long Poll...")
    server = await bot.api.messages.get_long_poll_server()
    
    while True:
        try:
            resp = await bot.api.http_client.request_json(
                f"https://{server.server}?act=a_check&key={server.key}&ts={server.ts}&wait=25&mode=2"
            )
            for update in resp.get("updates", []):
                if update[0] == 4:
                    await handler(update[1])
            server.ts = resp["ts"]
        except Exception as e:
            print(f"ERROR: {e}")
            await asyncio.sleep(3)

def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())

if __name__ == "__main__":
    asyncio.run(poll())
else:
    run()
