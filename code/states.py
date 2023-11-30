from aiogram.fsm.state import State, StatesGroup


class SetTokenState(StatesGroup):
    add_user = State()


class SetAmountForPollState(StatesGroup):
    set_amount = State()


class SetSpotifyUrl(StatesGroup):
    set_url = State()


class AvailableUrl(StatesGroup):
    available = State()
