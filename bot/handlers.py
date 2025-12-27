import re
from typing import Callable
from .config import config
from .state import ChatState

# цены → баф
PRICE_TO_BLESSING = {
    352: "Благословение атаки",
    351: "Благословение защиты",
    350: "Благословение удачи",
    349: "Благословение нежити",
    348: "Благословение демона",
    347: "Благословение человека",
}


def expected_after_tax(price: int) -> int:
    return round(price * 0.9)


COMMAND_PATTERN = re.compile(r"передать\s+(\d+)\s+золота", re.IGNORECASE)
SYSTEM_LOG_PATTERN = re.compile(r"получено\s+(\d+)\s+золота", re.IGNORECASE)
MANUAL_BLESS_PATTERN = re.compile(
    r"благословение атаки|благословение защиты|благословение удачи|"
    r"благословение нежити|благословение демона|благословение человека",
    re.IGNORECASE,
)


async def handle_command_message(msg: dict, state: ChatState) -> None:
    peer_id = msg.get("peer_id")
    if peer_id != config.peer_id:
        return

    text = msg.get("text", "")
    msg_id = msg.get("id")
    from_id = msg.get("from_id")

    if not from_id or from_id == config.bot_id:
        return

    m = COMMAND_PATTERN.search(text)
    if not m:
        return

    price = int(m.group(1))
    blessing = PRICE_TO_BLESSING.get(price)
    if not blessing:
        print(f"❌ Нет бафа для {price} золота")
        return

    state.clear_expired_pending()
    state.add_pending(from_id, price, msg_id, blessing)
    print(f"📝 ЖДЁМ ЛОГ: user {from_id}, цена {price}, msg {msg_id}, баф {blessing}")


async def handle_system_log(
    msg: dict,
    state: ChatState,
    send_blessing: Callable[[str, int], "object"],
):
    peer_id = msg.get("peer_id")
    from_id = msg.get("from_id")
    text = msg.get("text", "")
    msg_id = msg.get("id")

    if peer_id != config.peer_id or from_id != config.system_bot_id:
        return

    m = SYSTEM_LOG_PATTERN.search(text)
    if not m:
        return

    got_gold = int(m.group(1))
    state.clear_expired_pending()

    for user_id, (price, cmd_msg_id, blessing, ts) in list(state.pending.items()):
        expected = expected_after_tax(price)
        if got_gold == expected:
            print(
                f"✅ ЛОГ ПОДТВЕРЖДЁН: цена {price}, после налога {got_gold}, баф {blessing}"
            )
            await state.handle_blessing(blessing, cmd_msg_id, send_blessing)
            del state.pending[user_id]
            break


async def handle_manual_bless(msg: dict, state: ChatState):
    peer_id = msg.get("peer_id")
    text = msg.get("text", "")
    from_id = msg.get("from_id")
    msg_id = msg.get("id")

    if peer_id != config.community_peer_id:
        return

    if not from_id or from_id == config.bot_id:
        return

    if MANUAL_BLESS_PATTERN.search(text):
        print(f"🔔 РУЧНОЙ БАФ [{msg_id}] '{text[:50]}' — КД 61s")
        state.update_last_bless_time(extra=config.manual_bless_cd)
