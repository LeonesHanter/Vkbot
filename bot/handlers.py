import asyncio
import time
import logging
from vkbottle.bot import Message
from .state import StateManager

# Словарь соответствия золота и благословений
GOLD_TO_BLESSING = {
    99: "благословение атаки",
    100: "благословение защиты",
    101: "благословение удачи",
    102: "благословение человека",
    103: "благословение гнома",
    104: "благословение эльфа",
    105: "благословение орка",
    106: "благословение демона",
    107: "благословение гоблина",
}

# Словарь соответствия 303 (последовательность)
SPECIAL_GOLD = {
    303: ["благословение защиты", "благословение атаки", "благословение удачи"]
}

class ChatState:
    def __init__(self, chat_id: int, cooldown: int, max_requests: int, state_manager: StateManager, target_user_id: int):
        self.chat_id = chat_id
        self.cooldown = cooldown
        self.max_requests = max_requests
        self.peer_id = 2000000000 + chat_id
        self.state_manager = state_manager
        self.target_user_id = target_user_id  # ID сообщества, куда отправляются благословения
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(3)
        # Время последнего благословения (вручную или через бота)
        self.last_bless_time = 0

    def update_last_bless_time(self):
        self.last_bless_time = time.time()

    def is_in_cooldown(self):
        return (time.time() - self.last_bless_time) < self.cooldown

    async def handle_gold_message(self, api, gold_amount: int, original_user_message_id: int):
        queue = self.state_manager.get_queue(self.chat_id)

        # Проверяем, в cooldown ли бот
        if self.is_in_cooldown():
            # Если в cooldown, ставим в очередь
            if gold_amount in SPECIAL_GOLD:
                blessings = SPECIAL_GOLD[gold_amount]
                for blessing in blessings:
                    queue.append((blessing, original_user_message_id))
            else:
                blessing = GOLD_TO_BLESSING.get(gold_amount)
                if blessing:
                    queue.append((blessing, original_user_message_id))
            logging.info(f"Blessing for {gold_amount} gold added to queue for chat {self.chat_id} due to cooldown.")
        else:
            # Если не в cooldown, обновляем время и отправляем
            self.update_last_bless_time()
            if gold_amount in SPECIAL_GOLD:
                blessings = SPECIAL_GOLD[gold_amount]
                for blessing in blessings:
                    await self._send_blessing(api, blessing, original_user_message_id)
                    await asyncio.sleep(self.cooldown)
            else:
                blessing = GOLD_TO_BLESSING.get(gold_amount)
                if blessing:
                    await self._send_blessing(api, blessing, original_user_message_id)

        # Запускаем обработку очереди, если она не запущена
        if queue and not self.state_manager.is_processing(self.chat_id):
            self.state_manager.set_processing(self.chat_id, True)
            asyncio.create_task(self._process_queue(api))

    async def _process_queue(self, api):
        queue = self.state_manager.get_queue(self.chat_id)
        while queue:
            blessing, message_id = queue.pop(0)
            # Ждём, пока пройдёт cooldown
            remaining = self.cooldown - (time.time() - self.last_bless_time)
            if remaining > 0:
                await asyncio.sleep(remaining)
            # Обновляем время и отправляем
            self.update_last_bless_time()
            await self._send_blessing(api, blessing, message_id)
        self.state_manager.set_processing(self.chat_id, False)

    async def _send_blessing(self, api, blessing: str, message_id: int):
        # Используем target_user_id вместо peer_id чата
        peer_id = self.target_user_id  # Это будет -183040898

        try:
            await api.messages.send(
                peer_id=peer_id,
                message=blessing,
                forward_messages=[message_id],  # Пересылаем оригинальное сообщение пользователя
                disable_mentions=1,
                random_id=time.time_ns() % 1000000000
            )
            logging.info(f"Sent blessing '{blessing}' to user {peer_id}, forwarded message ID: {message_id}")
        except Exception as e:
            logging.error(f"Failed to send blessing to user {peer_id}: {e}")
