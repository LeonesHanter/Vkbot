import re
import logging
from typing import Dict, Any
from bot.config import config
from bot.state import StateManager
from bot.utils import get_player_name, parse_buff_price

logger = logging.getLogger(__name__)

async def handle_command_message(msg: Dict[str, Any], state: StateManager):
    """Обработка команд 'передать X золота' в чате 7"""
    peer_id = msg.get('peer_id', 0)
    text = msg.get('text', '').lower().strip()
    msg_id = msg.get('id', 0)

    # Только чат 7
    if peer_id != 2000000000 + config.main_chat_id:
        return

    # Парсим "передать 352 золота"
    match = re.match(r'передать\s+(\d+)\s*золота', text)
    if not match:
        return

    price = int(match.group(1))
    user_id = msg.get('from_id', 0)

    # Определяем баф по цене
    buff_type = parse_buff_price(price)
    if not buff_type:
        return

    # Добавляем в pending
    state.add_pending_request(
        chat_id=config.main_chat_id,
        user_id=user_id,
        price=price,
        msg_id=msg_id,
        buff_type=buff_type
    )

    # Ответим на команду
    await send_message(
        peer_id=peer_id,
        message=f"↳ {buff_type}",
        reply_to=msg_id
    )
    print(f"[COMMAND] ✅ {buff_type} от {user_id}")

async def handle_system_log(msg: Dict[str, Any], state: StateManager):
    """Обработка системных логов '🌕[id] получено X золота от [id]'"""
    text = msg.get('text', '')
    peer_id = msg.get('peer_id', 0)
    msg_id = msg.get('id', 0)

    # Только чат 7
    if peer_id != 2000000000 + config.main_chat_id:
        return

    # Парсим "🌕[id1060206296|Вечный], получено 316 золота от игрока [id215829857|Анастасия]!"
    payment_match = re.search(
        r'🌕\[id(\d+)\|.*?\],\s*получено\s*\d+\s*золота\s*от\s*игрока\s*\[id(\d+)\|',
        text
    )

    if payment_match:
        receiver_id = int(payment_match.group(1))
        player_id = int(payment_match.group(2))

        if receiver_id == config.receiver_id:
            # Обрабатываем оплату
            processed = state.process_player_payment(
                player_id=player_id,
                log_msg_id=msg_id,
                chat_id=config.main_chat_id
            )
            if processed:
   print(f"[SYSTEM] ✅ Деньги от {player_id}")

async def handle_manual_bless(msg: Dict[str, Any], state: StateManager):
    """✅ ЛС -183040898: умная очередь для сообщества"""
    peer_id = msg.get('peer_id', 0)
    text = msg.get('text', '').lower()

    # Только ЛС сообщества
    if peer_id != config.community_peer_id or "благословение" not in text:
        return

    chat_id = config.main_chat_id
    # Парсим точный тип бафа из текста ЛС
    buff_match = re.search(r'благословение\s+(\w+)', text)
    buff_type = buff_match.group(1).title() if buff_match else "ручной баф ЛС"

    state.manual_buff_issued(chat_id, buff_type)
    print(f"[MANUAL] ✅ ЛС '{buff_type}' → обработано")

async def handle_all_messages(msg: Dict[str, Any], state: StateManager):
    """Главная точка входа - маршрутизатор"""
    try:
        peer_id = msg.get('peer_id', 0)

        # Игнорируем свои сообщения
        if msg.get('from_id') == config.bot_owner_id:
            return

        # Команды чата 7
        if peer_id == 2000000000 + config.main_chat_id:
            await handle_command_message(msg, state)
            await handle_system_log(msg, state)

        # ЛС сообщества
        elif peer_id == config.community_peer_id:
            await handle_manual_bless(msg, state)

    except Exception as e:
   logger.error(f"[HANDLER ERROR] {e}")
        print(f"[HANDLER ERROR] {e}")

# Экспорт для main.py
__all__ = [
    'handle_all_messages',
    'handle_command_message',
    'handle_system_log',
    'handle_manual_bless'
]
