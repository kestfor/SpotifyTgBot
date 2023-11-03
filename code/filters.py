from data_base import db
from aiogram.filters import BaseFilter
from aiogram.types import Message


class EmptyDataBaseFilter:

    def __call__(self, *args, **kwargs):
        return not db.is_active()
