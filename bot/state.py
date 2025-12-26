import time
from typing import Dict, List, Tuple

class StateManager:
    def __init__(self):
        # cooldown для каждого чата
        self.last_bless_time_per_chat: Dict[int, float] = {}
        # очередь для каждого чата
        self.queues_per_chat: Dict[int, List[Tuple[str, int]]] = {}
        # обработка очереди
        self.is_processing_per_chat: Dict[int, bool] = {}

    def get_last_bless_time(self, chat_id: int) -> float:
        return self.last_bless_time_per_chat.get(chat_id, 0)

    def set_last_bless_time(self, chat_id: int, timestamp: float):
        self.last_bless_time_per_chat[chat_id] = timestamp

    def get_queue(self, chat_id: int):
        if chat_id not in self.queues_per_chat:
            self.queues_per_chat[chat_id] = []
        return self.queues_per_chat[chat_id]

    def is_processing(self, chat_id: int) -> bool:
        return self.is_processing_per_chat.get(chat_id, False)

    def set_processing(self, chat_id: int, value: bool):
        self.is_processing_per_chat[chat_id] = value