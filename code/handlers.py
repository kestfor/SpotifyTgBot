import asyncio

from aiogram.dispatcher.router import Router
from aiogram import F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.filters.callback_data import CallbackData
from spotify_api import spotify, AsyncSpotify
from data_base import db
from filters import EmptyDataBaseFilter
from states import SetTokenState

router = Router()


class AddSongCallbackFactory(CallbackData, prefix="fabAddSong"):
    uri: str


class ChangeSongsVote(CallbackData, prefix="fabAddVote"):
    uri: str
    action: str


async def handle_connection_error(callback: CallbackQuery | Message):
    text = ('не удалось обнаружить активное устройство spotify 😞\n\n'
            'для обнаружения устройства:\n\n'
            '1) запустите приложение spotify и любой трек/альбом на устройстве, управление которым вы хотите '
            'осуществлять\n\n'
            '2) заново запустите сессию в боте\n (/start)')
    if isinstance(callback, CallbackQuery):
        msg = await callback.message.edit_text(text=text)
        user_id = callback.from_user.id
    else:
        msg = await callback.answer(text=text)
        user_id = callback.from_user.id
    db.update_last_message(user_id, msg)


async def get_menu_text():
    mode = "share" if db.mode == db.SHARE_MODE else "poll"
    curr_track = await spotify.get_curr_track()
    if curr_track is None:
        text = f'🎹 режим: {mode}\n\n🔥 людей в сессии: {len(db.users)}'
    else:
        artists, name = curr_track
        text = (f'🎧: {name}\n\n'
                f"{'😎' * len(artists)}️: {', '.join(artists)}\n\n"
                f"🎹 режим: {mode}\n\n"
                f'🔥 людей в сессии: {len(db.users)}')
    return text


def get_admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="посмотреть токен", callback_data="view_token"))
    builder.row(InlineKeyboardButton(text='изменить режим', callback_data="change_mode"))
    builder.row(InlineKeyboardButton(text='🎵 добавить трек 🎵', callback_data='add_track'))
    builder.row(InlineKeyboardButton(text="❌ завершить сессию ❌", callback_data="confirm_end_session"))
    builder.row(InlineKeyboardButton(text="🔄 обновить 🔄", callback_data='menu'))
    builder.row(InlineKeyboardButton(text="⏮", callback_data="previous_track"))
    builder.add(InlineKeyboardButton(text="⏯", callback_data="start_pause"))
    builder.add(InlineKeyboardButton(text="⏭", callback_data="next_track"))
    return builder.as_markup()


def get_user_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="посмотреть токен", callback_data="view_token"))
    builder.row(InlineKeyboardButton(text='🎵 добавить трек 🎵', callback_data="add_track"))
    builder.row(InlineKeyboardButton(text="🔄обновить🔄", callback_data='menu'))
    if db.mode == db.SHARE_MODE:
        builder.row(InlineKeyboardButton(text="⏮", callback_data="previous_track"))
        builder.add(InlineKeyboardButton(text="⏯", callback_data="start_pause"))
        builder.add(InlineKeyboardButton(text="⏭", callback_data="next_track"))
    return builder.as_markup()


def get_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='в меню', callback_data='menu'))
    return builder.as_markup()


async def admin_start(message: Message):
    builder = InlineKeyboardBuilder()
    if db.is_active():
        msg = await message.answer(text=f"сессия запущена 🔥\ntoken: {db.token}", reply_markup=get_menu_keyboard())
    else:
        builder.row(InlineKeyboardButton(text="начать сессию", callback_data='start_session'))
        msg = await message.answer("Spotify 🎧", reply_markup=builder.as_markup())
    db.update_last_message(message.from_user.id, msg)


async def user_start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="ввести токен", callback_data='set_token'))
    msg = await message.answer("Spotify 🎧", reply_markup=builder.as_markup())
    db.update_last_message(message.from_user.id, msg)


async def menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        text = await get_menu_text()
    except ConnectionError:
        await handle_connection_error(callback)
        return
    if user_id in db.admins:
        keyboard = get_admin_menu_keyboard()
        msg = await callback.message.edit_text(text=text, reply_markup=keyboard)
    elif user_id in db.users:
        keyboard = get_user_menu_keyboard()
        msg = await callback.message.edit_text(text=text, reply_markup=keyboard)
    db.update_last_message(user_id, msg)


@router.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery):
    await menu(callback)


@router.callback_query(F.data != "start_session", EmptyDataBaseFilter())
async def handle_not_active_session(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins:
        msg = await callback.message.edit_text("сессия завершена, для запуска сессии используйте команду '/start'",
                                               reply_markup=None)
    else:
        msg = await callback.message.edit_text("сессия завершена, обратитесь к админам для ее запуска")
    await asyncio.sleep(5)
    await callback.message.delete()


@router.callback_query(F.data == 'change_mode')
async def change_mode(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='share ♻️', callback_data="set_share_mode"))
    builder.row(InlineKeyboardButton(text='poll ✅❎', callback_data='set_poll_mode'))
    msg = await callback.message.edit_text(text='выберите режим', reply_markup=builder.as_markup())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_share_mode')
async def set_share_mode(callback: CallbackQuery):
    db.mode = db.SHARE_MODE
    msg = await callback.message.edit_text(text='установлен режим share ♻️', reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_poll_mode')
async def set_share_mode(callback: CallbackQuery):
    db.mode = db.POLL_MODE
    msg = await callback.message.edit_text(text='установлен режим poll ✅❎', reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.message(Command("start"))
async def start_by_command(message: Message):
    try:
        await db.del_last_message(message.from_user.id)
    except:
        pass
    await asyncio.sleep(0.2)
    user_id = message.from_user.id
    await asyncio.sleep(0.3)
    if user_id in db.admins:
        await admin_start(message)
    else:
        await user_start(message)
    await message.delete()


@router.callback_query(F.data == 'start_session')
async def start_session(callback: CallbackQuery):
    db.set_token()
    try:
        global spotify
        spotify = AsyncSpotify()
        await spotify.authorize()
    except:
        await handle_connection_error(callback)
    else:
        msg = await callback.message.edit_text(text=f"сессия запущена 🔥\n"
                                                    f"token: {db.token}", reply_markup=get_menu_keyboard())
        db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'view_token')
async def view_token(callback: CallbackQuery):
    msg = await callback.message.edit_text(f"token: {db.token}", reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_token')
async def set_user_token(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.edit_text("введите токен")
    db.update_last_message(callback.from_user.id, msg)
    await state.set_state(SetTokenState.add_user)


@router.message(F.text.len() > 0, SetTokenState.add_user)
async def add_user_to_session(message: Message, state: FSMContext):
    token = message.text
    user_id = message.from_user.id
    print(user_id)
    print(message.from_user.username)
    if db.token == token:
        await db.del_last_message(user_id)
        await asyncio.sleep(0.3)
        db.add_user(user_id)
        msg = await message.answer(text="вы подключились к сессии", reply_markup=get_user_menu_keyboard())
        await message.delete()
        await state.clear()
    else:
        await db.del_last_message(user_id)
        await asyncio.sleep(0.3)
        msg = await message.answer(text='введен неверный токен или сессия не начата')
        await message.delete()
    db.update_last_message(user_id, msg)


@router.callback_query(F.data == "add_track")
async def search_track_callback(callback: CallbackQuery):
    db.update_last_message(callback.from_user.id, await callback.message.edit_text("введите поисковой запрос 🔎"))


@router.message(F.text)
async def search_track_handler(message: Message):
    if db.is_active():
        await db.del_last_message(message.from_user.id)
        user_id = message.from_user.id
        if user_id in db.users:
            try:
                list_of_results = await spotify.search(message.text)
            except ConnectionError:
                await handle_connection_error(message)
                return
            keyboard = InlineKeyboardBuilder()
            request = {}
            for item in list_of_results:
                song_info = ' - '.join(item[0:2])
                raw_uri = item[-1]
                request[raw_uri] = song_info
                keyboard.button(text=song_info, callback_data=AddSongCallbackFactory(uri=raw_uri))
            db.update_last_request(user_id, request)
            keyboard.adjust(1)
            keyboard.row(InlineKeyboardButton(text='назад', callback_data='menu'))
            msg = await message.answer("выберите результат поиска 😊", reply_markup=keyboard.as_markup())
            await message.delete()
        else:
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text='ввести токен', callback_data="set_token"))
            msg = await message.answer(text='необходимо подключиться к сессии ⌨️', reply_markup=builder.as_markup())
            await message.delete()
        db.update_last_message(user_id, msg)
    else:
        await db.del_last_message(message.from_user.id)
        await asyncio.sleep(0.3)
        msg = await message.answer("сессия завершена, для запуска сессии используйте команду '/start'",
                                   reply_markup=None)
        await message.delete()
        db.update_last_message(message.from_user.id, msg)


@router.callback_query(AddSongCallbackFactory.filter())
async def make_poll(callback: CallbackQuery, callback_data: AddSongCallbackFactory, bot: Bot):
    raw_uri = callback_data.uri
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.SHARE_MODE:
        try:
            await spotify.add_track_to_queue(spotify.get_full_uri(raw_uri))
        except ConnectionError:
            await handle_connection_error(callback)
        else:
            msg = await callback.message.edit_text("трек добавлен в очередь 👌", reply_markup=get_menu_keyboard())
            db.update_last_message(user_id, msg)
    elif db.mode == db.POLL_MODE:
        db.add_song_to_poll(raw_uri)
        msg = await callback.message.edit_text("трек выставлен на голосование 👌", reply_markup=get_menu_keyboard())
        db.update_last_message(user_id, msg)
        builder = InlineKeyboardBuilder()
        builder.button(text="✅", callback_data=ChangeSongsVote(uri=raw_uri, action="add"))
        builder.button(text="❎", callback_data=ChangeSongsVote(uri=raw_uri, action="ignore"))
        for user in db.users:
            if user != callback.from_user.id:
                msg = await bot.send_message(text=f"добавить в очередь "
                                                  f"{db.last_request[callback.from_user.id][raw_uri]}?",
                                             chat_id=user,
                                             reply_markup=builder.as_markup())
                db.update_last_message(user, msg)


@router.callback_query(ChangeSongsVote.filter())
async def check_vote(callback: CallbackQuery, callback_data: ChangeSongsVote):
    try:
        amount_votes = db.get_amount_votes(callback_data.uri)
        if callback_data.action == 'add':
            amount_votes += 1
    except KeyError:
        await callback.message.edit_text("голосование за этот трек уже не актуально 😔", reply_markup=None)
    else:
        await callback.message.edit_text(text=f"голос учтен 😉, 'за' проголосовал(о) "
                                              f"{amount_votes} человек(а)",
                                         reply_markup=None)
        if callback_data.action == 'add':
            try:
                db.add_vote(callback_data.uri)
            except ConnectionError:
                pass
    await asyncio.sleep(2)
    await callback.message.delete()


@router.callback_query(F.data == 'start_pause')
async def start_pause_track(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.SHARE_MODE:
        try:
            await spotify.start_pause()
        except ConnectionError:
            pass


@router.callback_query(F.data == 'next_track')
async def next_track(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.SHARE_MODE:
        try:
            await spotify.next_track()
        except ConnectionError:
            pass
        await asyncio.sleep(5)
        await menu(callback)


@router.callback_query(F.data == 'previous_track')
async def previous_track(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.SHARE_MODE:
        try:
            await spotify.previous_track()
        except ConnectionError:
            pass
        await asyncio.sleep(5)
        await menu(callback)


@router.callback_query(F.data == 'confirm_end_session')
async def confirm_end_session(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅", callback_data="end_session"))
    builder.add(InlineKeyboardButton(text='❎', callback_data="menu"))
    msg = await callback.message.edit_text(text="вы действительно хотите завершить сессию?",
                                           reply_markup=builder.as_markup())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'end_session')
async def end_session(callback: CallbackQuery, bot: Bot):
    for user in db.users:
        if user not in db.admins:
            msg = await bot.send_message(chat_id=user, text="сессия завершена, для ее начала обратитесь к админам",
                                         reply_markup=None)
        else:
            msg = await bot.send_message(chat_id=user,
                                         text='сессия завершена, для начала новой используйте команду "/start"',
                                         reply_markup=None)
        await db.del_last_message(user)
        db.update_last_message(user, msg)
    db.clear(last_message=True)
    await spotify.close()
