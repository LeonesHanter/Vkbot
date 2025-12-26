import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ChatConfig:
    enabled: bool = True
    chat_id: int = 110  # ID беседы (НЕ peer_id!)
    cooldown: int = 300  # Секунды между бафами
    max_requests: int = 5  # Максимум бафов за сессию

@dataclass
class BotConfig:
    token: str = os.getenv("VK_USER_TOKEN", "")  # 🔥 ТОКЕН ПОЛЬЗОВАТЕЛЯ
    source_chat_id: int = 110  # Основной чат для авто-сообщений
    target_user_id: int = 0  # НЕ НУЖЕН для user token
    log_file: str = "/home/FOK/vk-bots/Vkbot/bot.log"  # Полный путь для systemd
    
    chats: List[ChatConfig] = field(default_factory=lambda: [
        ChatConfig(chat_id=110, enabled=True, cooldown=300, max_requests=5),
        # Добавьте свои чаты:
        # ChatConfig(chat_id=123, enabled=True, cooldown=180, max_requests=10),
    ])

def load_config() -> BotConfig:
    """Загружает конфигурацию для USER TOKEN"""
    config = BotConfig()
    
    # 🔥 ПРОВЕРКА USER TOKEN
    if not config.token:
        raise ValueError("❌ VK_USER_TOKEN не найден в .env! Используйте токен пользователя!")
    
    # Проверка прав токена (messages обязательно)
    if "messages" not in config.token and "offline" not in config.token:
        logging.warning("⚠️  В токене нет прав 'messages' или 'offline'!")
    
    active_chats = [c for c in config.chats if c.enabled]
    if not active_chats:
        raise ValueError("❌ Нет активных чатов в конфиге!")
    
    print(f"✅ User Token конфиг загружен:")
    print(f"   Токен: {'*' * 10}...{config.token[-4:]}")
    print(f"   Source chat: {config.source_chat_id}")
    print(f"   Активных чатов: {len(active_chats)}")
    for chat in active_chats:
        print(f"     - Chat {chat.chat_id} (cooldown={chat.cooldown}s, max={chat.max_requests})")
    
    return config
