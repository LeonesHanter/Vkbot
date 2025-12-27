import time
import asyncio
from collections import deque
from typing import Deque, Dict, Tuple, Callable


class ChatState:
    def __init__(self, chat_id: int, cooldown: int,
                 pending_timeout: int, max_requests: int):
        self.chat_id = chat_id
        self.cooldown = cooldown
        self.pending_timeout = pending_timeout
        self.max_requests = max_requests

        self.last_bless_time: float = 0.0
        self.processing: bool = False
        self.queue: Deque[Tuple[str, int]] = deque()

        # user_id → (price, msg_id_команды, blessing, created_ts)
        self.pending: Dict[int, Tuple[int, int, str, float]] = {}

        self.request_count: int = 0

    def update_last_bless_time(self, extra: int = 0) -> None:
        self.last_bless_time = time.time() + extra

    def is_in_cooldown(self) -> bool:
        return (time.time() - self.last_bless_time) < self.cooldown

    def add_pending(self, user_id: int, price: int,
                    msg_id: int, blessing: str) -> None:
        self.pending[user_id] = (price, msg_id, blessing, time.time())

    def clear_expired_pending(self) -> None:
        now = time.time()
        to_delete = [uid for uid, (_, _, _, ts) in self.pending.items()
                     if now - ts > self.pending_timeout]
        for uid in to_delete:
            del self.pending[uid]

    async def handle_blessing(
        self,
        blessing: str,
        msg_id: int,
        send_func: Callable[[str, int], "asyncio.Future"],
    ):
        if self.is_in_cooldown() or self.processing:
            self.queue.append((blessing, msg_id))
            print(f"⏳ {blessing} в очереди")
            return

        self.processing = True
        try:
            self.update_last_bless_time()
            self.request_count += 1
            await send_func(blessing, msg_id)
            await asyncio.sleep(self.cooldown)
        finally:
            self.processing = False
            if self.queue:
                next_bless, next_msg = self.queue.popleft()
                asyncio.create_task(
                    self.handle_blessing(next_bless, next_msg, send_func)
                )


class StateManager:
    def __init__(self, config):
        self.chat_states: Dict[int, ChatState] = {}
        for chat_cfg in config.chats:
            if chat_cfg.enabled:
                self.chat_states[chat_cfg.chat_id] = ChatState(
                    chat_id=chat_cfg.chat_id,
                    cooldown=chat_cfg.cooldown,
                    pending_timeout=config.pending_timeout,
                    max_requests=chat_cfg.max_requests,
                )

    def get_chat_state(self, chat_id: int) -> ChatState:
        return self.chat_states[chat_id]
