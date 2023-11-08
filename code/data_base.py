import datetime
import os
import json
from config_reader import config
from utils import generate_token
from scheduler import scheduler
from aiogram.types import Message
from spotify import AsyncSpotify


class DataBase:

    __POLL_MODE = 0
    __SHARE_MODE = 1
    __MINUTES_FOR_POLL = 5
    __AMOUNT_TO_ADD_TO_QUEUE = 2

    def __init__(self):
        self._DATA_PATH = config.data_path.get_secret_value()
        self._token = None
        self._mode = self.__SHARE_MODE
        self._admins = self._load_admins()
        self._users = set([key for key in self._admins])
        self._poll_results = {}
        self._last_request = {}
        self._last_message_from_bot = {}

    def is_active(self):
        return self._token is not None

    def clear(self, **kwargs):
        """

        :param kwargs: last_message=True means that all will be cleared except last_message
        :return:
        """
        if kwargs["last_message"]:
            copy = self._last_message_from_bot.copy()
            self.__init__()
            self._last_message_from_bot = copy
        else:
            self.__init__()

    def add_user(self, chat_id):
        self._users.add(chat_id)

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
        tmp = self.__load_dict("admins.json")
        res = {}
        for key, value in tmp.items():
            res[int(key)] = value
        return res

    @property
    def AMOUNT_TO_ADD_TO_QUEUE(self):
        return self.__AMOUNT_TO_ADD_TO_QUEUE

    @AMOUNT_TO_ADD_TO_QUEUE.setter
    def AMOUNT_TO_ADD_TO_QUEUE(self, amount: int):
        if isinstance(amount, int) and amount >= 0:
            self.__AMOUNT_TO_ADD_TO_QUEUE = amount
        else:
            raise ValueError

    def del_user(self, user_id):
        self._users.remove(user_id)

    def del_admin(self, user_id):
        self._admins.pop(user_id)

    @property
    def amount_to_add_to_queue(self):
        return self.__AMOUNT_TO_ADD_TO_QUEUE

    @property
    def users(self):
        return self._users.copy()

    @property
    def POLL_MODE(self):
        return self.__POLL_MODE

    @property
    def SHARE_MODE(self):
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
        if new_mode in [self.__SHARE_MODE, self.__POLL_MODE]:
            self._mode = new_mode
        else:
            raise ValueError("wrong mode")

    def add_song_to_poll(self, uri: str):
        if uri not in self._poll_results:
            self._poll_results[uri] = 1
            run_date = datetime.datetime.now() + datetime.timedelta(minutes=self.__MINUTES_FOR_POLL)
            scheduler.add_job(self.del_song_from_poll, run_date=run_date, uri=uri)

    def del_song_from_poll(self, uri: str):
        if uri in self._poll_results:
            self._poll_results.pop(uri)

    def add_vote(self, uri: str, spotify: AsyncSpotify):
        if uri in self._poll_results:
            self._poll_results[uri] += 1
            if self._poll_results[uri] >= self.__AMOUNT_TO_ADD_TO_QUEUE:
                spotify.add_track_to_queue(spotify.get_full_uri(uri))
                self.del_song_from_poll(uri)
                scheduler.remove_job(uri)
        else:
            raise KeyError("uri is not valid")

    def get_amount_votes(self, uri: str):
        return self._poll_results[uri]

    def update_last_request(self, user_id, items: dict):
        self._last_request[user_id] = {}
        for key in items:
            self._last_request[user_id][key] = items[key]

    @property
    def last_request(self):
        return self._last_request.copy()


db = DataBase()
