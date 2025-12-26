import os
import logging
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()  # Загружаем .env

@dataclass
class ChatConfig:
    enabled: bool = True
    chat_id: int = 110  # ID беседы (vk.com/im?sel=c110)
    cooldown: int = 300  # Секунды между бафами
    max_requests: int = 5  # Максимум бафов за сессию

@dataclass
class BotConfig:
    token: str = os.getenv("VK_USER_TOKEN", "")
    source_chat_id: int = 110
    target_user_id: int = 0
    log_file: str = "/home/FOK/vk-bots/Vkbot/bot.log"
    
    chats: List[ChatConfig] = field(default_factory=lambda: [
        ChatConfig(chat_id=110, enabled=True, cooldown=300, max_requests=5),
        # Добавьте свои чаты сюда:
        # ChatConfig(chat_id=123, enabled=True, cooldown=180, max_requests=10),
    ])

def load_config() -> BotConfig:
    config = BotConfig()
    
    # Проверки
    if not config.token:
        raise ValueError("❌ VK_USER_TOKEN не найден в .env!")
    
    if not config.token.startswith("vk1."):
        logging.warning("⚠️  Токен должен начинаться с 'vk1.a.'")
    
    active_chats = [c for c in config.chats if c.enabled]
    if not active_chats:
        raise ValueError("❌ Нет активных чатов в конфиге!")
    
    logging.info("✅ User Token конфиг загружен:")
    logging.info(f"   Токен: {'*' * 10}...{config.token[-4:]}")
    logging.info(f"   Source chat: {config.source_chat_id}")
    logging.info(f"   Активных чатов: {len(active_chats)}")
    
    print(f"✅ Конфиг OK | Чатов: {len(active_chats)} | Токен: {config.token[:10]}...")
    return config
