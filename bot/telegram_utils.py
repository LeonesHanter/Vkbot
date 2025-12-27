import time
import logging
import requests
from .config import config

_last_tg_error = ""
_last_tg_error_time = 0.0
_ERROR_REPEAT_WINDOW = 60  # сек, в течение которых однотипную ошибку не шлём


def send_tg_alert(message: str):
    global _last_tg_error, _last_tg_error_time

    if not config.telegram_token or not config.telegram_chat_id:
        logging.warning("Telegram token/chat_id не заданы, алерт пропущен")
        return

    now = time.time()
    if message == _last_tg_error and now - _last_tg_error_time < _ERROR_REPEAT_WINDOW:
        return

    url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
    data = {"chat_id": config.telegram_chat_id, "text": message}
    try:
        resp = requests.post(url, data=data, timeout=5)
        if resp.status_code == 200:
            _last_tg_error = message
            _last_tg_error_time = now
        else:
            logging.error(f"TG alert failed: {resp.text}")
    except Exception as e:
        logging.error(f"TG alert exception: {e}")
