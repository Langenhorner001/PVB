from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from db import get_user


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            user = await get_user(event.from_user.id)
            if user and user.get("is_banned"):
                await event.answer("🚫 You have been banned from using this bot.")
                return
        return await handler(event, data)
