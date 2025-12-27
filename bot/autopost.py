import asyncio
import time
import json
import os
from .config import config
from .utils import send_message

STATE_FILE = "autopost_state.json"

AUTO_MESSAGE = (
    "🦊🍂Мадам Лисичка готова сделать Вас сильнее🍂🦊\n\n"
    "‼️Автобаф, автопост‼️\n\n"
    "⚔️Благословение атаки  — 352 \n"
    "🛡️Благословение защиты — 351 \n"
    "🍀Благословение удачи — 350 \n"
    "☠️Благословение нежити — 349 \n"
    "👺Благословение демона — 348\n"
    "🦸Благословение человека (иногда) — 347\n\n"
    "Шанс крита с колечком 51-52%\n\n"
    "Возможны задержки из-за очереди. При возникновении проблем — в [https://vk.com/lesyalutokvinova|лс]"
)

POST_COOLDOWN = 3 * 60 * 60  # 3 часа

def load_last_post_time():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('last_post_time', 0)
        except:
            pass
    return 0

def save_last_post_time(timestamp):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'last_post_time': timestamp}, f)
    except Exception as e:
        print(f"[AUTOPOST] Не удалось сохранить состояние: {e}")

async def auto_post_loop(session):
    global _last_post_time
    
    _last_post_time = load_last_post_time()
    now = time.time()
    
    if now - _last_post_time < POST_COOLDOWN:
        remaining = POST_COOLDOWN - (now - _last_post_time)
        hours_left = remaining / 3600
        print(f"[AUTOPOST] ✅ КД загружен! Следующий пост через {hours_left:.1f}ч")
    else:
        print("[AUTOPOST] ✅ Нет активного КД")
    
    while True:
        try:
            now = time.time()
            if now - _last_post_time < POST_COOLDOWN:
                remaining = POST_COOLDOWN - (now - _last_post_time)
                if remaining % 3600 < 60:
                    print(f"[AUTOPOST] ⏳ Осталось {remaining/3600:.1f}ч")
                await asyncio.sleep(300)
                continue
            
            print("[AUTOPOST] 📤 Отправляем пост...")
            peer_id = config.peer_id
            success = await send_message(
                session=session,
                token=config.token,
                peer_id=peer_id,
                message=AUTO_MESSAGE,
                reply_to=None,
            )
            
            if success:
                _last_post_time = now
                save_last_post_time(now)
                print(f"[AUTOPOST] ✅ Пост отправлен! КД обновлён (3ч)")
            else:
                print("[AUTOPOST] ❌ Ошибка отправки")
                await asyncio.sleep(3600)
                continue
                
            await asyncio.sleep(POST_COOLDOWN)
            
        except Exception as e:
            print(f"[AUTOPOST] Ошибка: {e}")
            await asyncio.sleep(3600)




