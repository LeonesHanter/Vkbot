from dataclasses import dataclass, field
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ChatConfig:
    chat_id: int
    enabled: bool = True
    cooldown: int = 61          # КД между бафами в этом чате
    max_requests: int = 100     # запас на будущее


@dataclass
class Config:
    token: str = os.getenv("VK_USER_TOKEN", "")
    log_file: str = os.getenv("LOG_FILE", "bot.log")

    # основной игровой чат
    main_chat_id: int = 215
    peer_id: int = field(init=False)

    # бот/сообщество логов золота
    system_bot_id: int = -183040898
    source_chat_id: int = 215          # если логи в этом же чате

    # чат/ЛС с сообществом, где вручную жмут бафы
    community_peer_id: int = -183040898

    # id нашего аккаунта (опционально, можно определить по первым сообщениям)
    bot_id: int = 0

    # времена
    cooldown: int = 61          # базовый КД бафа
    manual_bless_cd: int = 61   # доп. КД после ручного бафа
    pending_timeout: int = 15   # ожидание лога после команды

    # telegram
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_admin_ids: List[int] = field(default_factory=list)

    # список чатов
    chats: List[ChatConfig] = field(default_factory=lambda: [
        ChatConfig(chat_id=215, enabled=True, cooldown=61, max_requests=100),
    ])

    def __post_init__(self):
        if not self.token:
            raise ValueError("VK_USER_TOKEN не найден в .env")
        self.peer_id = 2000000000 + self.main_chat_id

        admins = os.getenv("TELEGRAM_ADMIN_IDS", "")
        if admins:
            self.telegram_admin_ids = [
                int(a.strip()) for a in admins.split(",") if a.strip().isdigit()
            ]


config = Config()
