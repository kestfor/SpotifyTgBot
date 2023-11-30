import os
import json
from config_reader import config
from utils import generate_token
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class DataBase:

    __RESTRICTED_MODE = 0
    __SHARE_MODE = 1
    __AMOUNT_TO_ADD_TO_QUEUE = 5
    __FULL_UPDATE_TIMEOUT_SECONDS = 20

    def __init__(self):
        self._DATA_PATH = config.data_path.get_secret_value()
        if not os.path.exists(self._DATA_PATH):
            os.system(f"mkdir {self._DATA_PATH}")
        self._admins_file_name = config.admin_file.get_secret_value()
        if self._DATA_PATH not in self._admins_file_name:
            raise ValueError("путь к файлу с администраторами должен проходить через 'data_path'")
        self._token = None
        self._mode = self.__SHARE_MODE
        self._admins = self._load_admins()
        self._users = self._admins.copy()
        self._last_request = {}
        self._last_message_from_bot = {}
        self._scheduler: AsyncIOScheduler = None
        self._users_queue = []
        self._scheduler_jobs = {}

    @property
    def scheduler(self):
        return self._scheduler

    def is_active(self):
        return self._token is not None

    async def include_update_functions(self, functions: list, args: list[list]):
        for num, func in enumerate(functions, start=0):
            self._scheduler.add_job(func, "interval", seconds=self.__FULL_UPDATE_TIMEOUT_SECONDS, args=args[num], replace_existing=True)

    def add_scheduler(self, scheduler):
        self._scheduler = scheduler

    def clear(self):
        scheduler = self._scheduler
        copy_last_message = self._last_message_from_bot.copy()
        self.__init__()
        self._last_message_from_bot = copy_last_message
        self._scheduler = scheduler

    def add_user(self, chat_id, user_name=None):
        self._users[chat_id] = user_name

    def __load_dict(self, file_name) -> dict:
        if os.path.exists(f"{self._DATA_PATH}/{file_name}") and os.path.getsize(f"{self._DATA_PATH}/{file_name}") > 0:
            with open(f"{self._DATA_PATH}/{file_name}", "r", encoding="utf-8") as file:
                res = json.load(file)
                return res
        return {}

    def __update_file(self, data, file_name) -> None:
        with open(f"{self._DATA_PATH}/{file_name}", "w", encoding="utf-8") as file:
            if data is not None and len(data) > 0:
                file.write(json.dumps(data, ensure_ascii=False, indent=4))

    def _load_admins(self) -> dict:
        tmp = self.__load_dict(self._admins_file_name)
        res = {}
        for key, value in tmp.items():
            res[int(key)] = value
        return res

    @property
    def amount_to_add_to_queue(self):
        return self.__AMOUNT_TO_ADD_TO_QUEUE

    @amount_to_add_to_queue.setter
    def amount_to_add_to_queue(self, amount: int):
        if isinstance(amount, int) and amount >= 0:
            self.__AMOUNT_TO_ADD_TO_QUEUE = amount
        else:
            raise ValueError

    def del_user(self, user_id):
        self._users.pop(user_id)
        if user_id in db.admins:
            self.del_admin(user_id)

    def del_admin(self, user_id):
        self._admins.pop(user_id)

    @property
    def users(self):
        return self._users.copy()

    @property
    def restricted_mode(self):
        return self.__RESTRICTED_MODE

    @property
    def share_mode(self):
        return self.__SHARE_MODE

    @property
    def last_message(self):
        return self._last_message_from_bot

    def update_last_message(self, user_id, message: Message):
        self._last_message_from_bot[user_id] = message

    async def del_last_message(self, user_id):
        if user_id in self._last_message_from_bot:
            await self._last_message_from_bot[user_id].delete()
            self._last_message_from_bot.pop(user_id)

    @property
    def admins(self):
        return self._admins.copy()

    @property
    def token(self):
        return self._token

    def set_token(self):
        self._token = generate_token(20)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, new_mode: int):
        if new_mode in [self.__SHARE_MODE, self.__RESTRICTED_MODE]:
            self._mode = new_mode
        else:
            raise ValueError("wrong mode")

    def add_song_to_users_queue(self, user_id, song_id):
        self._users_queue.append((user_id, song_id))

    def del_song_from_users_queue(self, user_id, song_id):
        if (user_id, song_id) in self._users_queue:
            self._users_queue.remove((user_id, song_id))

    @property
    def user_queue(self):
        return self._users_queue

    @user_queue.setter
    def user_queue(self, item):
        if isinstance(item, list):
            self._users_queue = item

    def add_admin(self, user_id, user_name):
        self._admins[user_id] = user_name

    def update_last_request(self, user_id, items: dict):
        self._last_request[user_id] = {}
        for key in items:
            self._last_request[user_id][key] = items[key]

    @property
    def last_request(self):
        return self._last_request.copy()


db = DataBase()
