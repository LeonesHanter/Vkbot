cd /home/FOK/vk-bots/Vkbot/bot
cat > main.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import sys
import time
import os
import re
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# ЛОГИ В JOURNALCTL
print("🚀 BotBuff CHAT 215 ЗАПУЩЁН!")

TOKEN = os.getenv("VK_USER_TOKEN")
if not TOKEN:
    print("❌ VK_USER_TOKEN!")
    sys.exit(1)

print(f"✅ Токен: {TOKEN[:15]}...")
CHAT_ID = 215
PEER_ID = 2000000000 + CHAT_ID
print(f"🎯 Чат {CHAT_ID} | peer_id {PEER_ID}")

async def send_buff(session, gold):
    data = {
        'peer_id': PEER_ID,
        'message': f"💰 Баф за {gold} золота! ✨",
        'random_id': int(time.time() * 1000000),
        'access_token': TOKEN,
        'v': '5.131'
    }
    async with session.post('https://api.vk.com/method/messages.send', data=data) as resp:
        print(f"✅ БАФ {gold} ОТПРАВЛЕН!")

async def process_msg(msg):
    text = msg.get('text', '').lower()
    print(f"📨 peer_id={msg.get('peer_id')} | '{text[:50]}'")
    
    if msg.get('peer_id') == PEER_ID and 'получено' in text and 'золота' in text:
        nums = re.findall(r'\d+', text)
        if nums:
            gold = int(nums[0])
            print(f"🪙 НАЙДЕНО {gold} ЗОЛОТА!")
            async with aiohttp.ClientSession() as session:
                await send_buff(session, gold)

async def main():
    print("🔄 Long Poll...")
    async with aiohttp.ClientSession() as session:
        # Long Poll сервер
        async with session.get('https://api.vk.com/method/messages.getLongPollServer', 
                              params={'access_token': TOKEN, 'v': '5.131'}) as resp:
            lp = (await resp.json())['response']
            print(f"📡 {lp['server']}")
            
            ts = lp['ts']
            while True:
                try:
                    url = f"https://{lp['server']}?act=a_check&key={lp['key']}&ts={ts}&wait=25&mode=2&version=3"
                    async with session.get(url) as r:
                        data = await r.json()
                        ts = data['ts']
                        
                        for update in data.get('updates', []):
                            if update[0] == 4:
                                await process_msg(update[1])
                except Exception as e:
                    print(f"⚠️ {e}")
                    await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
else:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
EOF
