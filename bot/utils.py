import time
from typing import Optional, Dict, Any

import aiohttp


async def get_long_poll_server(session: aiohttp.ClientSession,
                               token: str) -> Dict[str, Any]:
    async with session.get(
        "https://api.vk.com/method/messages.getLongPollServer",
        params={"access_token": token, "v": "5.131"},
    ) as resp:
        data = await resp.json()
        return data["response"]


async def get_message(session: aiohttp.ClientSession, token: str,
                      msg_id: int) -> Optional[Dict[str, Any]]:
    data = {"message_ids": msg_id, "access_token": token, "v": "5.131"}
    try:
        async with session.post(
            "https://api.vk.com/method/messages.getById", data=data
        ) as resp:
            result = await resp.json()
            items = result.get("response", {}).get("items")
            return items[0] if items else None
    except Exception:
        return None


async def send_message(
    session: aiohttp.ClientSession,
    token: str,
    peer_id: int,
    message: str,
    reply_to: Optional[int],
) -> bool:
    data = {
        "peer_id": peer_id,
        "message": message,
        "random_id": int(time.time() * 1_000_000),
        "access_token": token,
        "v": "5.131",
    }
    if reply_to is not None:
        data["reply_to"] = reply_to
    try:
        async with session.post(
            "https://api.vk.com/method/messages.send", data=data
        ) as resp:
            await resp.json()
            return resp.status == 200
    except Exception:
        return False


