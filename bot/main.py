#!/usr/bin/env python3
import asyncio
import sys
import time
import os
import re
from dotenv import load_dotenv
import requests
from vkbottle import Bot

# Логи ВСЮДА (stdout + файл)
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 🔥 В JOURNALCTL
        logging.FileHandler('/home/FOK/vk-bots/Vkbot/bot.log')
    ]
)

load_dotenv()
print("🚀 BotBuff ЗАПУЩЕН!")

# Конфиг прямо в коде
TOKEN = os.getenv("VK_USER_TOKEN")
if not TOKEN:
    print("❌ VK_USER_TOKEN не найден!")
    sys.exit(1)

print(f"✅ Токен: {TOKEN[:15]}...")
CHAT_ID = 215  # 🔥 НОВЫЙ ЧАТ ID: 215

bot = Bot(token=TOKEN)

async def send_buff(peer_id, gold_amount):
    """Отправляет баф"""
    try:
        await bot.api.messages.send(
            peer_id=peer_id,
            message=f"💰 Баф за {gold_amount} золота! ✨",
            random_id=int(time.time() * 1000000)
        )
        print(f"✅ БАФ ОТПРАВЛЕН в {peer_id}")
    except Exception as e:
        print(f"❌ Ошибка бафа: {e}")

async def process_message(raw_msg):
    """Обрабатывает сообщение"""
    peer_id = raw_msg.get('peer_id')
    text = raw_msg.get('text', '').lower()
    
    print(f"📨 peer_id={peer_id} | text='{text[:50]}'")
    
    if peer_id == 2000000215 and 'получено' in text and 'золота' in text:  # 🔥 2000000215 для чата 215
        # Извлекаем число золота
        numbers = re.findall(r'\d+', text)
        if numbers:
            gold = int(numbers[0])
            print(f"🪙 НАЙДЕНО {gold} ЗОЛОТА!")
            await send_buff(peer_id, gold)

async def long_poll():
    """Главный цикл Long Poll"""
    print("🔄 Long Poll сервер...")
    
    # Получаем Long Poll сервер
    lp_server = await bot.api.messages.get_long_poll_server()
    print(f"📡 Сервер: {lp_server.server}")
    
    ts = lp_server.ts
    key = lp_server.key
    server = lp_server.server
    
    while True:
        try:
            # Запрос обновлений
            url = f"https://{server}"
            params = {
                'act': 'a_check',
                'key': key,
                'ts': ts,
                'wait': 25,
                'mode': 2,
                'version': 3
            }
            
            response = await bot.api.http_client.request_json(url, params=params)
            ts = response['ts']
            
            for update in response.get('updates', []):
                if update[0] == 4:  # Новое сообщение
                    await process_message(update[1])
                    
        except Exception as e:
            print(f"⚠️ Long Poll ошибка: {e}")
            await asyncio.sleep(3)

async def main():
    print(f"🎯 Ожидаю золото в чате {CHAT_ID} (peer_id=2000000{CHAT_ID})...")
    await long_poll()

def run_bot():
    """Для systemd"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Остановка")
    finally:
        print("👋 До свидания!")

if __name__ == "__main__":
    asyncio.run(main())
else:
    run_bot()
