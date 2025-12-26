from pydantic import BaseModel
from yaml import safe_load
from typing import List

class ChatConfig(BaseModel):
    chat_id: int
    cooldown: int = 60
    max_requests: int = 4
    enabled: bool = True

class BotConfig(BaseModel):
    source_chat_id: int
    target_user_id: int
    chats: List[ChatConfig]
    token: str
    log_file: str = "bot.log"

def load_config(path: str = "config.yaml") -> BotConfig:
    with open(path, 'r', encoding='utf-8') as f:
        data = safe_load(f)
    return BotConfig(**data)
