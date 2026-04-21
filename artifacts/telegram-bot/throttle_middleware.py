import time
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

_last_message: dict[int, float] = {}
RATE_LIMIT_SECONDS = 1.5


class ThrottleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
            now = time.monotonic()
            last = _last_message.get(uid, 0)
            if now - last < RATE_LIMIT_SECONDS:
                await event.answer("⏳ Please slow down. Send one message at a time.")
                return
            _last_message[uid] = now
        return await handler(event, data)
