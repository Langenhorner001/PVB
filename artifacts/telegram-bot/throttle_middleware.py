import time
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

_last_event: dict[int, float] = {}
RATE_LIMIT_SECONDS = 1.5


class ThrottleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        if isinstance(event, Message) and event.from_user:
            from_user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            from_user = event.from_user

        if from_user:
            uid = from_user.id
            now = time.monotonic()
            last = _last_event.get(uid, 0)
            if now - last < RATE_LIMIT_SECONDS:
                if isinstance(event, Message):
                    await event.answer("⏳ Please slow down. Send one message at a time.")
                else:
                    await event.answer("⏳ Slow down.", show_alert=False)
                return
            _last_event[uid] = now
        return await handler(event, data)
