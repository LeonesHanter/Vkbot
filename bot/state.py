import json
import time
import logging
from typing import Dict, Optional
from bot.config import config

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, config):
        self.config = config
        self.chat_states: Dict[int, 'ChatState'] = {}
        self.pending_requests: Dict[int, Dict] = {}

    def get_chat_state(self, chat_id: int) -> 'ChatState':
        if chat_id not in self.chat_states:
            self.chat_states[chat_id] = ChatState(chat_id)
        return self.chat_states[chat_id]

    def add_pending_request(self, chat_id: int, user_id: int, price: int, msg_id: int, buff_type: str):
        """Сохраняем запрос 'передать XXX золота'"""
        self.pending_requests[msg_id] = {
            'chat_id': chat_id,
            'user_id': user_id,
            'price': price,
            'msg_id': msg_id,
            'buff_type': buff_type,
            'timestamp': time.time(),
            'buff_issued': False
        }
        logger.info(f"[PENDING] user={user_id} передаёт {price} → {buff_type}")

    def process_player_payment(self, player_id: int, log_msg_id: int):
        """✅ НОВАЯ ЛОГИКА: обрабатывает оплату нашему боту"""
        for req_id, request in list(self.pending_requests.items()):
            if (request.get('user_id') == player_id and 
                not request.get('buff_issued')):
                
                logger.info(f"[BUFF] ✅ ОПЛАТА ПОДТВЕРЖДЕНА! user={player_id} → {request['buff_type']}")
                self.issue_buff(request['chat_id'], request)
                return True
        return False

    def issue_buff(self, chat_id: int, request: Dict):
        """Выдаёт баф"""
        try:
            buff_type = request['buff_type']
            user_id = request['user_id']
            
            # TODO: вызов VK API для бафа
            logger.info(f"[BUFF ISSUED] ✅ {buff_type} выдан user={user_id} в чат {chat_id}")
            request['buff_issued'] = True
            
            # Очистка pending
            self.pending_requests.pop(request['msg_id'], None)
            
        except Exception as e:
            logger.error(f"[BUFF] Ошибка выдачи бафа: {e}")

# Заглушка для ChatState (если нужно)
class ChatState:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.last_buff_time = 0
