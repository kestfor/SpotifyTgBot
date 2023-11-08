import time

from asyncspotify.client import get_id
from config_reader import config
import asyncspotify
import asyncspotify.http
import spotify_errors


class AsyncSpotify:

    class ModifiedHTTP(asyncspotify.http.HTTP):
        async def player_add_to_queue(self, uri: str, device_id):
            r = asyncspotify.Route('POST', f'me/player/queue?uri={uri}', device=device_id)
            await self.request(r)

    class ModifiedClient(asyncspotify.client.Client):

        def __init__(self, auth):
            self.auth = auth(self)
            self.http: AsyncSpotify.ModifiedHTTP = AsyncSpotify.ModifiedHTTP(self)

        async def player_add_to_queue(self, uri: str, device=None):
            await self.http.player_add_to_queue(uri, device_id=get_id(device))

    _prefix = 'spotify%3Atrack%3A'
    _update_timeout = 5
    _volume_step = 5

    def __init__(self):
        self._client_id = config.spotify_client_id.get_secret_value()
        self._client_secret = config.spotify_client_secret.get_secret_value()
        self._spotify_username = config.spotify_username.get_secret_value()
        self._redirect_uri = config.spotify_redirect_uri.get_secret_value()
        self._scope = asyncspotify.Scope(user_modify_playback_state=True, user_read_playback_state=True)
        self._token_file = '../data/secret.json'

        self._auth = asyncspotify.EasyAuthorizationCodeFlow(
            client_id=self._client_id,
            client_secret=self._client_secret,
            scope=self._scope,
            storage=self._token_file
        )

        self._session = AsyncSpotify.ModifiedClient(self._auth)
        self._volume = 100
        self._saved_volume = self._volume
        self._playing: bool = True
        self._cached_currently_playing: asyncspotify.CurrentlyPlaying = None
        self._last_update_time = 0

    async def authorize(self):
        await self._session.authorize()
        try:
            player = await self._session.get_player()
            device = player.device
            self._playing = player.is_playing
            self._volume = device.volume_percent
            self._saved_volume = self._volume
        except asyncspotify.exceptions.NotFound:
            raise spotify_errors.ConnectionError("there is no active device")

    async def close(self):
        await self._session.close()

    async def force_update(self):
        self._cached_currently_playing = await self._session.player_currently_playing()

    async def update(self):
        now = time.time()
        if (now - self._last_update_time) >= self._update_timeout:
            await self.force_update()


    @staticmethod
    async def __get_info(item) -> list[list[str]]:
        """
        collects artist, track, uri from search request and pack to list
        :param item:
        :return: list of lists of artist, track, uri
        """
        res = []
        for i in item["tracks"]:
            res.append([i.artists[0].name, i.name, i.id])
        return res

    @staticmethod
    def get_full_uri(uri: str):
        if uri.find(AsyncSpotify._prefix) == -1:
            return AsyncSpotify._prefix + uri

    async def get_curr_track(self):
        try:
            await self.update()
            currently_playing = self._cached_currently_playing
            curr_track = currently_playing.track
            artists = [artist.name for artist in curr_track.artists]
            name = curr_track.name
            return [artists, name]
        except:
            raise spotify_errors.ConnectionError

    async def add_track_to_queue(self, uri):
        try:
            await self._session.player_add_to_queue(uri)
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        except:
            raise spotify_errors.ConnectionError

    async def next_track(self):
        try:
            await self._session.player_next()
            self._playing = True
            await self.force_update()
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        except:
            raise spotify_errors.ConnectionError

    async def previous_track(self):
        try:
            await self._session.player_prev()
            self._playing = True
            await self.force_update()
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        except:
            raise spotify_errors.ConnectionError

    async def start_pause(self):
        try:
            currently_playing = await self._session.player_currently_playing()
            if currently_playing.is_playing:
                self._playing = False
                await self._session.player_pause()
            else:
                self._playing = True
                await self._session.player_play()
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        except:
            raise spotify_errors.ConnectionError

    async def increase_volume(self):
        try:

            await self._session.player_volume(min(100, self._volume + self._volume_step))
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        else:
            self._volume = min(100, self._volume + self._volume_step)

    async def decrease_volume(self):
        try:
            await self._session.player_volume(max(0, self._volume - self._volume_step))
        except asyncspotify.Forbidden:
            raise spotify_errors.PremiumRequired
        else:
            self._volume = max(0, self._volume - self._volume_step)

    async def mute_unmute(self):
        old_values = [self._volume, self._saved_volume]
        try:
            if self._volume == 0:
                self._volume = self._saved_volume
            else:
                self._saved_volume = self._volume
                self._volume = 0
            await self._session.player_volume(self._volume)
        except asyncspotify.Forbidden:
            self._volume, self._saved_volume = old_values
            raise spotify_errors.PremiumRequired

    @property
    def volume(self):
        return self._volume

    @property
    def is_playing(self):
        print(self._playing)
        return self._playing

    async def search(self, request: str) -> list[list[str]]:
        """
        :param request: запрос
        :return: список с id, автором, названием
        """
        try:
            return await self.__get_info(await self._session.search("track", q=request, limit=10))
        except:
            raise spotify_errors.ConnectionError
