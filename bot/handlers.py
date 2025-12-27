import re
import logging
from bot.config import config
from bot.state import state_manager

logger = logging.getLogger(__name__)

async def handle_system_log(msg, state, send_buff_callback):
    """✅ НОВАЯ ЛОГИКА: '🌕[bot_id], получено XXX от игрока YYY'"""
    message_text = msg.get('text', '')
    from_id = msg.get('from_id', 0)
    
    # Проверяем лог от системного бота
    if (from_id == config.system_bot_id and 
        "🌕" in message_text and 
        "получено" in message_text and 
        "золота" in message_text):
        
        # 🌕123456, получено 316 золота от игрока 215829857
        bot_match = re.search(r'🌕(\d+),', message_text)
        player_match = re.search(r'игрока\s+(\d+)', message_text)
        
        if bot_match and player_match:
            bot_id_from_log = int(bot_match.group(1))
            player_id = int(player_match.group(1))
            
            # Деньги пришли НАШЕМУ боту?
            if bot_id_from_log == config.bot_id:
                logger.info(f"[SYSTEM] Деньги от игрока {player_id} → нашему боту {config.bot_id}")
                
                # Проверяем pending запросы
                if state_manager.process_player_payment(player_id, msg['id']):
                    logger.info(f"[HANDLER] Баф выдан по логам!")
                else:
                    logger.info(f"[HANDLER] Оплата от {player_id}, но pending не найдено")

async def handle_command_message(msg, state):
    """Обработка команд 'передать 352 золота'"""
    text = msg.get('text', '').lower()
    user_id = msg.get('from_id')
    msg_id = msg.get('id')
    
    # Парсим "передать 352 золота"
    transfer_match = re.search(r'передать\s+(\d+)\s+золота', text)
    
    if transfer_match:
        amount = int(transfer_match.group(1))
        chat_id = msg.get('peer_id', config.peer_id) - 2000000000
        
        # Определяем тип бафа по сумме
        buff_type = get_buff_by_price(amount)
        
        if buff_type:
            state_manager.add_pending_request(chat_id, user_id, amount, msg_id, buff_type)
            logger.info(f"[COMMAND] {user_id} передаёт {amount} → {buff_type}")

def get_buff_by_price(price: int) -> str:
    """Определяет баф по цене"""
    price_map = {
        352: "Благословение атаки",
        351: "Благословение защиты", 
        350: "Благословение удачи",
        349: "Благословение нежити",
        348: "Благословение демона",
        347: "Благословение человека"
    }
    return price_map.get(price, None)
