from dataclasses import dataclass, field
from typing import List
import os
from dotenv import load_dotenv
import vk_api

load_dotenv()

@dataclass
class ChatConfig:
    chat_id: int
    enabled: bool = True
    cooldown: int = 61
    max_requests: int = 100

@dataclass
class Config:
    token: str = os.getenv("VK_USER_TOKEN", "")
    log_file: str = os.getenv("LOG_FILE", "bot.log")
    source_chat_id: int = 7
    main_chat_id: int = 7
    community_peer_id: int = -183040898

    cooldown: int = 61
    manual_bless_cd: int = 61
    pending_timeout: int = 30

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_admin_ids: List[int] = field(default_factory=list)

    chats: List[ChatConfig] = field(default_factory=lambda: [
        ChatConfig(chat_id=7, enabled=True, cooldown=61, max_requests=100),
    ])

    def __post_init__(self):
        if not self.token:
            raise ValueError("VK_USER_TOKEN не найден в .env")
        self.peer_id = 2000000000 + self.main_chat_id

        # ✅ АВТООПРЕДЕЛЕНИЕ BOT_ID + receiver_id
        try:
            vk_session = vk_api.VkApi(token=self.token)
            user_info = vk_session.get_api().users.get(v=5.131)[0]
            self.bot_id = user_info['id']
            self.receiver_id = self.bot_id
            print(f"[CONFIG] Bot ID определён: {self.bot_id}")
        except Exception as e:
            print(f"[CONFIG] Ошибка определения bot_id: {e}")
            self.bot_id = 0
            self.receiver_id = 0

        admins = os.getenv("TELEGRAM_ADMIN_IDS", "")
        if admins:
            self.telegram_admin_ids = [int(a.strip()) for a in admins.split(",") if a.strip().isdigit()]

config = Config()
