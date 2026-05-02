from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from db import get_user


class BanCheckMiddleware(BaseMiddleware):
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
            user = await get_user(from_user.id)
            if user and user.get("is_banned"):
                if isinstance(event, Message):
                    await event.answer("🚫 You have been banned from using this bot.")
                else:
                    await event.answer("🚫 You have been banned.", show_alert=True)
                return
        return await handler(event, data)
