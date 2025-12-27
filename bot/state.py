import json
import time
import logging
import vk_api
from typing import Dict, Optional
from bot.config import config
from collections import deque

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, config):
        self.config = config
        self.chat_states: Dict[int, 'ChatState'] = {}
        self.pending_requests: Dict[int, Dict] = {}
        self.request_queues: Dict[int, deque] = {}
        self.vk_session = vk_api.VkApi(token=config.token)
        self.vk = self.vk_session.get_api()

    def get_chat_state(self, chat_id: int) -> 'ChatState':
        if chat_id not in self.chat_states:
            self.chat_states[chat_id] = ChatState(chat_id)
            self.request_queues[chat_id] = deque()
        return self.chat_states[chat_id]

    def add_pending_request(self, chat_id: int, user_id: int, price: int, msg_id: int, buff_type: str):
        self.pending_requests[msg_id] = {
            'chat_id': chat_id, 'user_id': user_id, 'price': price,
            'original_msg_id': msg_id,
            'buff_type': buff_type,
            'timestamp': time.time(), 'buff_issued': False
        }
        print(f"[PENDING] ✅ {buff_type}")
        return True

    def cleanup_expired_pending(self):
        now = time.time()
        expired = []
        for msg_id, request in self.pending_requests.items():
            if now - request['timestamp'] > config.pending_timeout:
                expired.append(msg_id)
        for msg_id in expired:
            self.pending_requests.pop(msg_id, None)
        return len(expired)

    def process_player_payment(self, player_id: int, log_msg_id: int, chat_id: int = config.main_chat_id):
        chat_state = self.get_chat_state(chat_id)
        now = time.time()

        for req_id, request in list(self.pending_requests.items()):
            if (request.get('user_id') == player_id and
                request.get('chat_id') == chat_id and
                not request.get('buff_issued')):

                cd_left = now - chat_state.last_buff_time
                if cd_left < self.config.cooldown:
                    queue_item = {
                        'user_id': player_id, 
                        'price': request['price'],
                        'original_msg_id': request['original_msg_id'],
                        'buff_type': request['buff_type'],
                        'chat_id': chat_id
                    }
                    self.request_queues[chat_id].append(queue_item)
                    print(f"[PAYMENT QUEUE] ⏳ {player_id} в очередь #{len(self.request_queues[chat_id])} (CD={self.config.cooldown-cd_left:.0f}s)")
                    return True
                else:
                    self.issue_buff(chat_id, request)
                    self.pending_requests.pop(req_id, None)
                    print(f"[PAYMENT BUFF] ✅ {request['buff_type']} | очередь: {len(self.request_queues[chat_id])}")
                    return True
        return False

    def process_next_in_queue(self, chat_id: int):
        chat_state = self.get_chat_state(chat_id)
        now = time.time()

        if (now - chat_state.last_buff_time >= self.config.cooldown and
            self.request_queues.get(chat_id) and len(self.request_queues[chat_id]) > 0):

            next_request = self.request_queues[chat_id].popleft()
            request = {
                'chat_id': next_request['chat_id'],
                'buff_type': next_request['buff_type'],
                'original_msg_id': next_request['original_msg_id']
            }
            
            self.issue_buff(chat_id, request)
            print(f"[QUEUE ACTIVE] ✅ {next_request['buff_type']} | осталось: {len(self.request_queues[chat_id])}")

    def manual_buff_issued(self, chat_id: int, buff_type: str = "ручной баф"):
        """✅ ЛС: очередь=0+CD=0 → CD | очередь>0 → очередь | CD>0 → ПРОПУСК!"""
        chat_state = self.get_chat_state(chat_id)
        queue_len = len(self.request_queues.get(chat_id, []))
        now = time.time()
        cd_left = max(0, self.config.cooldown - (now - chat_state.last_buff_time))
        
        if queue_len == 0 and cd_left == 0:
            chat_state.last_buff_time = time.time()
            print(f"[MANUAL] ✅ ПУСТАЯ очередь + CD=0s → CD чат {chat_id}")
        elif queue_len > 0:
            log_msg_id = int(time.time())
            queue_item = {
                'user_id': 0, 'price': 0,
                'original_msg_id': log_msg_id,
                'buff_type': buff_type,
                'chat_id': chat_id
            }
            self.request_queues[chat_id].append(queue_item)
            print(f"[MANUAL QUEUE] ⏳ ЛС '{buff_type}' → очередь #{queue_len+1} (CD={cd_left:.0f}s НЕ трогаем!)")
        else:
            print(f"[MANUAL SKIP] ⏳ ЛС '{buff_type}' ПРОПУЩЕН (CD={cd_left:.0f}s активен!)")

    def issue_buff(self, chat_id: int, request: Dict):
        try:
            buff_name = request['buff_type']
            original_msg_id = request['original_msg_id']
            peer_id = 2000000000 + chat_id

            self.vk.messages.send(
                peer_id=peer_id,
                message=buff_name,
                reply_to=original_msg_id,
                random_id=int(time.time())
            )

            chat_state = self.get_chat_state(chat_id)
            chat_state.last_buff_time = time.time()
            print(f"[BUFF SENT] ✅ '{buff_name}' [reply_to={original_msg_id}]")

        except Exception as e:
            logger.error(f"[BUFF ERROR] {e}")

class ChatState:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.last_buff_time = 0
