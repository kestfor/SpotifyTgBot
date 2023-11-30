import asyncio
import os
import random
from aiogram.dispatcher.router import Router
from aiogram import F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters.callback_data import CallbackData
from spotify_errors import PremiumRequired, ConnectionError, AuthorizationError
from spotify import AsyncSpotify
from data_base import db
from filters import EmptyDataBaseFilter, UrlFilter
from aiogram.filters import CommandObject
from states import SetTokenState, SetSpotifyUrl, AvailableUrl
import qrcode

router = Router()
spotify: AsyncSpotify


class AddSongCallbackFactory(CallbackData, prefix="fabAddSong"):
    uri: str


class ViewQueueFactory(CallbackData, prefix="fabViewQueue"):
    id: str


class ChangeSongsVote(CallbackData, prefix="fabAddVote"):
    uri: str
    action: str


class ChangeDeviceFactory(CallbackData, prefix="fabDevice"):
    id: str
    is_active: bool


class AddAdminFactory(CallbackData, prefix="addAdmin"):
    user_id: int
    user_name: str


class GetNextLyrics(CallbackData, prefix="fabLyrics"):
    start_ind: int
    step: int
    action: str


async def synchronize_queues(spotify_queue):
    top_track = spotify_queue[0].id
    ids = [item[1] for item in db.user_queue]
    if top_track not in ids:
        db.user_queue = []
    else:
        top_track_ind = ids.index(top_track)
        db.user_queue = db.user_queue[top_track_ind:]


async def handle_connection_error(callback: CallbackQuery | Message, bot=None):
    user_id = callback.from_user.id
    text = 'ошибка соединения с Spotify 😞'
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="обновить", callback_data="refresh"))
    builder.row(InlineKeyboardButton(text='покинуть сессию', callback_data='leave_session'))
    if callback.from_user.id in db.admins:
        builder.row(InlineKeyboardButton(text='завершить сессию', callback_data="confirm_end_session"))
    if bot is None:
        if isinstance(callback, CallbackQuery):
            msg = await callback.message.edit_text(text=text, reply_markup=builder.as_markup())
            user_id = callback.from_user.id
        else:
            msg = await callback.answer(text=text, reply_markup=builder.as_markup())
            user_id = callback.from_user.id
        db.update_last_message(user_id, msg)
    else:
        try:
            message = callback
            msg = await bot.edit_message_text(chat_id=user_id, text=text, message_id=message.message_id,
                                              reply_markup=builder.as_markup())
            db.update_last_message(user_id, msg)
        except:
            pass


def get_volume_emoji(volume: int):
    volumes = "🔇🔈🔉🔊"
    if volume == 0:
        return volumes[0]
    elif 0 < volume <= 33:
        return volumes[1]
    elif 33 < volume <= 66:
        return volumes[2]
    elif 66 < volume <= 100:
        return volumes[3]


async def handle_premium_required_error(callback: CallbackQuery | Message):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='в меню', callback_data="menu"))
    if isinstance(callback, CallbackQuery):
        msg = await callback.message.edit_text("Для этой функции требуется spotify premium",
                                               reply_markup=builder.as_markup())
    else:
        msg = await callback.answer("Для этой функции требуется spotify premium", reply_markup=builder.as_markup())
    db.update_last_message(callback.from_user.id, msg)


async def get_menu_text():
    global spotify
    emoji_artists = '🥺🤫😐🙄😮😄😆🥹☺️🙂😌😙😎😏🤩😋🥶🥵🤭🤔😈'
    curr_track = await spotify.get_curr_track()
    if curr_track is None:
        text = f'🔥 людей в сессии: {len(db.users)}'
    else:
        volume = spotify.volume
        volume_str = f"{get_volume_emoji(volume)}: {volume}%\n\n" if spotify.is_playing else ""
        artists, name = curr_track
        text = (
                f"🎧: {name}\n\n{''.join(random.choices(emoji_artists, k=len(artists)))}️: {', '.join(artists)}\n\n" + volume_str +
                f"🔥 людей в сессии:"
                f" {len(db.users)}")
    return text


def get_settings_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="посмотреть токен", callback_data="view_token"))
    builder.row(InlineKeyboardButton(text='ссылка приглашение', callback_data="view_url"))
    builder.row(InlineKeyboardButton(text='QR-код', callback_data="view_qr"))
    builder.row(InlineKeyboardButton(text="сменить устройство", callback_data="view_devices"))
    if user_id in db.admins:
        builder.row(InlineKeyboardButton(text='изменить режим', callback_data="change_mode"))
        # builder.row(InlineKeyboardButton(text='добавить админа', callback_data="view_admins_to_add"))
    builder.row(InlineKeyboardButton(text='покинуть сессию', callback_data="leave_session"))
    if user_id in db.admins:
        builder.row(InlineKeyboardButton(text="завершить сессию", callback_data="confirm_end_session"))
    builder.row(InlineKeyboardButton(text='назад', callback_data="menu"))
    return builder.as_markup()


def get_admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚙️ настройки ⚙️", callback_data="get_settings"))
    builder.row(InlineKeyboardButton(text='🎵 добавить трек 🎵', callback_data='add_track'))
    builder.row(InlineKeyboardButton(text='💽 очередь 💽', callback_data="view_queue"))
    builder.row(InlineKeyboardButton(text='📖 текст песни 📖', callback_data="view_lyrics"))
    builder.row(InlineKeyboardButton(text='🔉', callback_data='decrease_volume'))
    builder.add(InlineKeyboardButton(text='🔇', callback_data='mute_volume'))
    builder.add(InlineKeyboardButton(text='🔊', callback_data="increase_volume"))
    builder.row(InlineKeyboardButton(text="🔄 обновить 🔄", callback_data='refresh'))
    builder.row(InlineKeyboardButton(text="⏮", callback_data="previous_track"))
    builder.add(InlineKeyboardButton(text="⏯", callback_data="start_pause"))
    builder.add(InlineKeyboardButton(text="⏭", callback_data="next_track"))
    return builder.as_markup()


def get_user_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚙️ настройки ⚙️", callback_data="get_settings"))
    builder.row(InlineKeyboardButton(text='🎵 добавить трек 🎵', callback_data="add_track"))
    builder.row(InlineKeyboardButton(text='💽 очередь 💽', callback_data="view_queue"))
    builder.row(InlineKeyboardButton(text='📖 текст песни 📖', callback_data="view_lyrics"))
    if db.mode == db.share_mode:
        builder.row(InlineKeyboardButton(text='🔉', callback_data='decrease_volume'))
        builder.add(InlineKeyboardButton(text='🔇', callback_data='mute_volume'))
        builder.add(InlineKeyboardButton(text='🔊', callback_data="increase_volume"))
    builder.row(InlineKeyboardButton(text="🔄обновить🔄", callback_data='refresh'))
    if db.mode == db.share_mode:
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
        msg = await message.answer(text=f"сессия запущена 🔥\ntoken: <code>{db.token}</code>",
                                   reply_markup=get_menu_keyboard(), parse_mode="HTML")
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
        await spotify.update()
        text = await get_menu_text()
    except ConnectionError:
        await handle_connection_error(callback)
        return
    if user_id in db.admins:
        keyboard = get_admin_menu_keyboard()
        msg = await callback.message.edit_text(text=text, reply_markup=keyboard)
    else:
        keyboard = get_user_menu_keyboard()
        msg = await callback.message.edit_text(text=text, reply_markup=keyboard)
    db.update_last_message(user_id, msg)


async def refresh(callback: CallbackQuery):
    old_text = callback.message.text
    try:
        await spotify.update()
        curr_text = await get_menu_text()
    except ConnectionError:
        await handle_connection_error(callback)
        return
    if old_text != curr_text:
        await menu(callback)
    else:
        return


async def get_queue_text():
    global spotify
    queue = await spotify.get_curr_user_queue()
    await synchronize_queues(queue)
    queue = queue[0:min(len(db.user_queue), 10)]
    if len(db.user_queue) == 0:
        return None
    else:
        text = ''
        ids = [item[1] for item in db.user_queue]
        for item in queue:
            author = '' if item.id not in ids else (' - поставил(а) @' + db.users[db.user_queue[ids.index(item.id)][0]])
            text += (item.name[:item.name.find('(')] if '(' in item.name else item.name) + author + '\n\n'
        return text


@router.callback_query(F.data == 'view_queue')
async def view_queue(callback: CallbackQuery):
    if db.is_active():
        queue = await get_queue_text()
        if queue is None or len(queue) == 0:
            msg = await callback.message.edit_text("в очереди нет треков", reply_markup=get_menu_keyboard())
        else:
            builder = InlineKeyboardBuilder()
            builder.button(text='в меню', callback_data="menu")
            builder.adjust(1)
            msg = await callback.message.edit_text("треки в очереди:\n\n" + queue, reply_markup=builder.as_markup())
        db.update_last_message(callback.from_user.id, msg)
    else:
        await handle_not_active_session(callback)


@router.callback_query(F.data == 'view_url')
async def view_url(callback: CallbackQuery):
    if db.is_active():
        url = f"t.me/SpotifyShareControlBot?start={db.token}"
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="назад", callback_data="get_settings"))
        msg = await callback.message.edit_text(text=url, reply_markup=builder.as_markup())
        db.update_last_message(message=msg, user_id=callback.from_user.id)
    else:
        await handle_not_active_session(callback)


def get_lyrics_switcher(start, end, step):
    builder = InlineKeyboardBuilder()
    if start != 0:
        builder.row(InlineKeyboardButton(text='◀️', callback_data=GetNextLyrics(start_ind=start - step, step=20,
                                                                                action='decrement').pack()))
    if end != -1:
        builder.add(InlineKeyboardButton(text='▶️', callback_data=GetNextLyrics(start_ind=start + step, step=20,
                                                                                action='increment').pack()))
    builder.row(InlineKeyboardButton(text='меню', callback_data="menu"))
    return builder.as_markup()


@router.callback_query(F.data == 'view_lyrics')
async def view_lyrics(callback: CallbackQuery):
    if db.is_active():
        # try:
        lyrics = await spotify.get_lyrics(callback.message.edit_text,
                                              text="ищу текст песни\nподождите чуток\nтекст сейчас появится 😉",
                                              reply_markup=get_menu_keyboard())
        # except ValueError:
        #     await callback.message.edit_text("не удалось найти текст", reply_markup=get_menu_keyboard())
        # else:
        await callback.message.edit_text('\n'.join(lyrics.list_lyrics[0:20]),
                                             reply_markup=get_lyrics_switcher(0, 20, 20))
    else:
        await handle_not_active_session(callback)


@router.callback_query(GetNextLyrics.filter(F.action == 'increment'))
async def next_part_lyrics(callback: CallbackQuery, callback_data: GetNextLyrics):
    lyrics = await spotify.get_lyrics()
    start_ind = callback_data.start_ind
    end_ind = min(start_ind + callback_data.step, len(lyrics.list_lyrics))
    end_ind_conv = end_ind if end_ind != len(lyrics.list_lyrics) else -1
    await callback.message.edit_text(text='\n'.join(lyrics.list_lyrics[start_ind:end_ind]),
                                     reply_markup=get_lyrics_switcher(start_ind, end_ind_conv, end_ind - start_ind))


@router.callback_query(GetNextLyrics.filter(F.action == 'decrement'))
async def previous_part_lyrics(callback: CallbackQuery, callback_data: GetNextLyrics):
    lyrics = await spotify.get_lyrics()
    start_ind = max(callback_data.start_ind, 0)
    end_ind = callback_data.step + start_ind
    await callback.message.edit_text(text='\n'.join(lyrics.list_lyrics[start_ind:end_ind]),
                                     reply_markup=get_lyrics_switcher(start_ind, end_ind, callback_data.step))


@router.callback_query(F.data == 'view_admins_to_add')
async def view_admins_to_add(callback: CallbackQuery):
    if db.is_active():
        builder = InlineKeyboardBuilder()
        for user_id, username in db.users:
            if user_id not in db.admins:
                builder.button(text=username, callback_data=AddAdminFactory(user_id=user_id, user_name=username))
        builder.button(text="назад", callback_data='menu')
        await callback.message.edit_text(text='выберите пользователя', reply_markup=builder.as_markup())
    else:
        await handle_not_active_session(callback)


@router.callback_query(AddAdminFactory.filter())
async def add_admin(callback: CallbackQuery, callback_data: AddAdminFactory, bot):
    db.add_admin(callback_data.user_id, callback_data.user_name)
    await callback.message.edit_text(text='добавлен новый администратор', reply_markup=get_menu_keyboard())
    users = set(db.users.keys())
    users.remove(callback_data.user_id)
    await update_menu_for_all_users(bot, users)


@router.callback_query(F.data == 'view_qr')
async def view_qr(callback: CallbackQuery, bot: Bot):
    if db.is_active():
        url = f"t.me/SpotifyShareControlBot?start={db.token}"
        img = qrcode.make(url)
        img.save("qr_token")
        document = FSInputFile("qr_token")
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="в меню", callback_data="back_from_qr"))
        msg = await bot.send_photo(photo=document, chat_id=callback.from_user.id,
                                   reply_markup=builder.as_markup())
        await db.del_last_message(callback.from_user.id)
        db.update_last_message(callback.from_user.id, msg)
        os.remove("qr_token")
    else:
        await handle_not_active_session(callback)


@router.callback_query(F.data == 'back_from_qr')
async def back_from_qr(callback: CallbackQuery, bot: Bot):
    text = await get_menu_text()
    if callback.from_user.id in db.admins:
        markup = get_admin_menu_keyboard()
    else:
        markup = get_user_menu_keyboard()
    msg = await bot.send_message(text=text, chat_id=callback.from_user.id, reply_markup=markup)
    await db.del_last_message(callback.from_user.id)
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == "refresh")
async def refresh_callback(callback: CallbackQuery):
    if db.is_active():
        await refresh(callback)
    else:
        await handle_not_active_session(callback)


@router.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery):
    await menu(callback)


@router.callback_query(F.data == 'start_playlist')
async def start_playlist_callback(callback: CallbackQuery):
    msg = await callback.message.edit_text("отправь ссылку на альбом/плейлист/артиста",
                                           reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.message(UrlFilter())
async def chose_url_role(message: Message, state: FSMContext, bot: Bot):
    st = await state.get_state()
    if st == SetSpotifyUrl.set_url:
        await set_spotify_url(message, state, bot)
    else:
        await start_playlist(message)


async def start_playlist(message: Message):
    await db.del_last_message(message.from_user.id)
    try:
        await spotify.start_playlist(message.text)
    except ValueError:
        msg = await message.answer(
            "неверная ссылка, необходима ссылка на spotify контент в виде автора, плейлиста или альбома",
            reply_markup=get_menu_keyboard())
        db.update_last_message(message.from_user.id, msg)
    except ConnectionError:
        await handle_connection_error(message)
    except PremiumRequired:
        await handle_premium_required_error(message)
    else:
        msg = await message.answer("плейлист успешно запущен", reply_markup=get_menu_keyboard())
        db.update_last_message(message.from_user.id, msg)
    await message.delete()


@router.callback_query(F.data == "view_devices")
async def view_devices(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    devices = await spotify.get_devices()
    for device in devices:
        text = device.name
        text = '🟢 ' + text if device.is_active else '🔴 ' + text
        keyboard.button(text=text, callback_data=ChangeDeviceFactory(id=device.id, is_active=device.is_active))
    keyboard.adjust(1)
    keyboard.row(InlineKeyboardButton(text="назад", callback_data="get_settings"))
    await callback.message.edit_text(text="доступные устройства Spotify", reply_markup=keyboard.as_markup())


@router.callback_query(ChangeDeviceFactory.filter())
async def transfer_playback(callback: CallbackQuery, callback_data: ChangeDeviceFactory):
    device_id = callback_data.id
    is_active = callback_data.is_active
    if is_active:
        await callback.message.edit_text("данное устройство уже является текущим устройством воспроизведения",
                                         reply_markup=get_menu_keyboard())
        return
    try:
        await spotify.transfer_player(device_id)
    except ConnectionError:
        await callback.message.edit_text("не удалось изменить устройство", reply_markup=get_menu_keyboard())
    else:
        await callback.message.edit_text("устройство воспроизведения успешно изменено",
                                         reply_markup=get_menu_keyboard())


@router.callback_query(F.data != "start_session", EmptyDataBaseFilter())
async def handle_not_active_session(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins:
        await callback.message.edit_text("сессия завершена, для запуска сессии используйте команду '/start'",
                                         reply_markup=None)
    else:
        await callback.message.edit_text("сессия завершена, обратитесь к админам для ее запуска")
    await asyncio.sleep(5)
    await callback.message.delete()


@router.callback_query(F.data == 'change_mode')
async def change_mode(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='share ♻️', callback_data="set_share_mode"))
    builder.row(InlineKeyboardButton(text='restricted 🔒', callback_data='set_restricted_mode'))
    msg = await callback.message.edit_text(text='выберите режим', reply_markup=builder.as_markup())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_share_mode')
async def set_share_mode(callback: CallbackQuery):
    db.mode = db.share_mode
    msg = await callback.message.edit_text(text='установлен режим share ♻️', reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_restricted_mode')
async def set_share_mode(callback: CallbackQuery):
    db.mode = db.restricted_mode
    msg = await callback.message.edit_text(text='установлен режим share restricted 🔒', reply_markup=get_menu_keyboard())
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'get_settings')
async def get_settings(callback: CallbackQuery):
    if db.is_active():
        msg = await callback.message.edit_text(text='⚙️ настройки ⚙️',
                                               reply_markup=get_settings_keyboard(callback.from_user.id))
        db.update_last_message(callback.from_user.id, msg)
    else:
        await handle_not_active_session(callback)


@router.message(Command("start"))
async def start_by_command(message: Message, command: CommandObject, bot: Bot):
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
        token = command.args
        if token is None or token == '':
            await user_start(message)
        else:
            db.update_last_message(user_id, message)
            await authorize(token, user_id, message.from_user.username, bot)
    await message.delete()


async def set_spotify_url(message: Message, state: FSMContext, bot: Bot):
    url = message.text
    await db.del_last_message(message.from_user.id)
    try:
        await spotify.authorize(url)
    except:
        await message.delete()
        msg = await message.answer("отправлена неверная ссылка")
        db.update_last_message(message.from_user.id, msg)
        return
    else:
        await state.clear()
        await message.delete()
        db.set_token()
        await db.include_update_functions([update_queue_for_all_users, update_menu_for_all_users], [[bot], [bot]])
        msg = await message.answer(text=f"авторизация прошла успешно, сессия запущена 🔥\n"
                                        f"token: <code>{db.token}</code>", reply_markup=get_menu_keyboard(),
                                   parse_mode="HTML")
        db.update_last_message(message.from_user.id, msg)


@router.callback_query(F.data == 'start_session')
async def start_session(callback: CallbackQuery, bot: Bot, state: FSMContext):
    try:
        global spotify
        spotify = AsyncSpotify()
        await spotify.authorize()
    except AuthorizationError:
        msg = await callback.message.edit_text(f"Необходима инициализация\n"
                                               f"Перейдите по ссылке: {await spotify.create_authorize_route()}\n"
                                               f"Отправьте ссылку, на которую вы были перенаправлены")
        db.update_last_message(callback.from_user.id, msg)
        await state.set_state(SetSpotifyUrl.set_url)
        return
    except:
        text = ('не удалось обнаружить активное устройство spotify 😞\n\n'
                'для обнаружения устройства:\n\n'
                '1) запустите приложение spotify и любой трек/альбом на устройстве, управление которым вы хотите '
                'осуществлять\n\n'
                '2) заново запустите сессию (/start)')
        await callback.message.edit_text(text=text, reply_markup=None)
    else:
        db.set_token()
        await db.include_update_functions([update_queue_for_all_users, update_menu_for_all_users], [[bot], [bot]])
        msg = await callback.message.edit_text(text=f"сессия запущена 🔥\n"
                                                    f"token: <code>{db.token}</code>", reply_markup=get_menu_keyboard(),
                                               parse_mode="HTML")
        db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'view_token')
async def view_token(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="назад", callback_data="get_settings"))
    msg = await callback.message.edit_text(f"token: <code>{db.token}</code>", reply_markup=builder.as_markup(),
                                           parse_mode="HTML")
    db.update_last_message(callback.from_user.id, msg)


@router.callback_query(F.data == 'set_token')
async def set_user_token(callback: CallbackQuery, state: FSMContext):
    msg = await callback.message.edit_text("введите токен")
    db.update_last_message(callback.from_user.id, msg)
    await state.set_state(SetTokenState.add_user)


async def authorize(token, user_id, user_name, bot: Bot):
    if db.token == token:
        await db.del_last_message(user_id)
        await asyncio.sleep(0.3)
        db.add_user(user_id, user_name)
        msg = await bot.send_message(text=await get_menu_text(), chat_id=user_id, reply_markup=get_user_menu_keyboard())
    else:
        await db.del_last_message(user_id)
        await asyncio.sleep(0.3)
        msg = await bot.send_message(chat_id=user_id, text='введен неверный токен или сессия не начата')
    db.update_last_message(user_id, msg)


@router.message(F.text.len() > 0, SetTokenState.add_user)
async def add_user_to_session(message: Message, state: FSMContext):
    token = message.text
    user_name = message.from_user.username
    user_id = message.from_user.id
    if db.token == token:
        await db.del_last_message(user_id)
        await asyncio.sleep(0.3)
        db.add_user(user_id, user_name)
        msg = await message.answer(text=await get_menu_text(), reply_markup=get_user_menu_keyboard())
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
    if db.is_active():
        db.update_last_message(callback.from_user.id,
                               await callback.message.edit_text("введите поисковой запрос 🔎",
                                                                reply_markup=get_menu_keyboard()))
    else:
        await handle_not_active_session(callback)


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
    try:
        await spotify.add_track_to_queue(raw_uri)
    except PremiumRequired:
        await handle_premium_required_error(callback)
    except ConnectionError:
        await handle_connection_error(callback)
    else:
        db.add_song_to_users_queue(user_id, raw_uri)
        msg = await callback.message.edit_text("трек добавлен в очередь 👌", reply_markup=get_menu_keyboard())
        await update_queue_for_all_users(bot)
        db.update_last_message(user_id, msg)


@router.callback_query(F.data == 'start_pause')
async def start_pause_track(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.share_mode:
        try:
            await spotify.start_pause()
        except PremiumRequired:
            await handle_premium_required_error(callback)
            return
        except ConnectionError:
            pass
        await menu(callback)
        await update_menu_for_all_users(bot, callback.from_user.id)


@router.callback_query(F.data == 'next_track')
async def next_track(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.share_mode:
        try:
            old_track = await spotify.get_curr_track()
            await spotify.next_track()
            while old_track == await spotify.get_curr_track():
                await asyncio.sleep(0.5)
                await spotify.force_update()
        except PremiumRequired:
            await handle_premium_required_error(callback)
            return
        except ConnectionError:
            pass
        await menu(callback)
        await update_menu_for_all_users(bot, callback.from_user.id)
        await update_queue_for_all_users(bot)


@router.callback_query(F.data == 'previous_track')
async def previous_track(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    user_id = callback.from_user.id
    if user_id in db.admins or db.mode == db.share_mode:
        try:
            old_track = await spotify.get_curr_track()
            await spotify.previous_track()
            while old_track == await spotify.get_curr_track():
                await asyncio.sleep(0.5)
                await spotify.force_update()
        except PremiumRequired:
            await handle_premium_required_error(callback)
            return
        except ConnectionError:
            pass
        await menu(callback)
        await update_menu_for_all_users(bot, callback.from_user.id)
        await update_queue_for_all_users(bot)


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
        try:
            if user not in db.admins:
                msg = await bot.send_message(chat_id=user, text="сессия завершена, для ее начала обратитесь к админам",
                                             reply_markup=None)
            else:
                msg = await bot.send_message(chat_id=user,
                                             text='сессия завершена, для начала новой используйте команду "/start"',
                                             reply_markup=None)
            await db.del_last_message(user)
            await del_message(msg)
        except:
            pass
    await spotify.close()
    db.clear()


async def del_message(msg: Message):
    await asyncio.sleep(5)
    await msg.delete()


@router.callback_query(F.data == 'increase_volume')
async def increase_volume(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    try:
        await spotify.increase_volume()
    except PremiumRequired:
        await handle_premium_required_error(callback)
        return
    except ConnectionError:
        pass
    await menu(callback)
    await update_menu_for_all_users(bot, callback.from_user.id)


@router.callback_query(F.data == 'decrease_volume')
async def decrease_volume(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    try:
        await spotify.decrease_volume()
    except PremiumRequired:
        await handle_premium_required_error(callback)
        return
    except ConnectionError:
        pass
    await menu(callback)
    await update_menu_for_all_users(bot, callback.from_user.id)


@router.callback_query(F.data == 'mute_volume')
async def mute_volume(callback: CallbackQuery, bot: Bot):
    if not db.is_active():
        await handle_not_active_session(callback)
        return
    try:
        await spotify.mute_unmute()
    except PremiumRequired:
        await handle_premium_required_error(callback)
        return
    except ConnectionError:
        pass
    await menu(callback)
    await update_menu_for_all_users(bot, callback.from_user.id)


@router.callback_query(F.data == 'leave_session')
async def leave_session(callback: CallbackQuery):
    user_id = callback.from_user.id
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅", callback_data="confirm_leave_session"))
    builder.add(InlineKeyboardButton(text='❎', callback_data="menu"))
    if user_id not in db.admins or len(db.admins) > 1:
        msg = await callback.message.edit_text(text='Вы уверены, что хотите покинуть сессию?',
                                               reply_markup=builder.as_markup())
        db.update_last_message(user_id, msg)
    else:
        await confirm_end_session(callback)


@router.callback_query(F.data == "confirm_leave_session")
async def confirm_leave_session(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in db.admins:
        db.del_admin(user_id)
    if user_id in db.users:
        db.del_user(user_id)
    await callback.message.edit_text(text='вы покинули сессию')
    await asyncio.sleep(5)
    await callback.message.delete()


async def update_menu_for_all_users(bot: Bot, *ignore_list):
    if db.is_active():
        curr = None
        for user_id, message in db.last_message.items():
            old: str = message.text
            if old.startswith("🎧"):
                if curr is None:
                    try:
                        curr = await get_menu_text()
                    except ConnectionError:
                        await handle_connection_error(message, bot)
                        return
                if user_id not in ignore_list:
                    old_split = old.split('\n\n')
                    old_split = [item[item.find(":") + 2:] for item in old_split]
                    curr_split = curr.split('\n\n')
                    curr_split = [item[item.find(":") + 2:] for item in curr_split]
                    if old_split != curr_split:
                        if user_id in db.admins:
                            markup = get_admin_menu_keyboard()
                        else:
                            markup = get_user_menu_keyboard()
                        try:
                            msg = await bot.edit_message_text(chat_id=user_id, text=curr, message_id=message.message_id,
                                                              reply_markup=markup)
                            db.update_last_message(user_id, msg)
                        except:
                            pass


async def update_queue_for_all_users(bot: Bot):
    if db.is_active():
        queue = None
        for user_id, message in db.last_message.items():
            old: str = message.text
            if old.startswith('треки в очереди') or old.startswith("в очереди нет треков"):
                if queue is None:
                    try:
                        queue = await get_queue_text()
                    except PremiumRequired:
                        await handle_connection_error(message, bot)
                        return
                    except ConnectionError:
                        await handle_premium_required_error(message)
                        return
                if queue is None:
                    new = "в очереди нет треков"
                else:
                    new = "треки в очереди:\n\n" + queue
                if old != new:
                    try:
                        msg = await bot.edit_message_text(chat_id=user_id, text=new, message_id=message.message_id,
                                                          reply_markup=get_menu_keyboard())
                        db.update_last_message(user_id, msg)
                    except:
                        pass
