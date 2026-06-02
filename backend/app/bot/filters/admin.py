from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.core.config import get_settings


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        settings = get_settings()
        return message.from_user.id in settings.admin_id_list


class NotBannedFilter(BaseFilter):
    async def __call__(self, message: Message, session=None) -> bool:
        if not session:
            return True
        from app.repositories import UserRepository
        repo = UserRepository(session)
        user = await repo.get_by_id(message.from_user.id)
        return user is None or not user.is_banned
