from data_base import db
from aiogram.types import Message


class EmptyDataBaseFilter:

    def __call__(self, *args, **kwargs):
        return not db.is_active()


class UrlFilter:

    def __call__(self, message: Message):
        return message.text.startswith("http")
