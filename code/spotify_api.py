import asyncio
import time

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
from config_reader import config
import asyncspotify


class Spotify:

    _prefix = 'spotify:track:'
    _update_seconds = 10
    _force_update_timeout = 1

    def __init__(self):
        self._client_id = config.spotify_client_id.get_secret_value()
        self._client_secret = config.spotify_client_secret.get_secret_value()
        self._spotify_username = config.spotify_username.get_secret_value()
        self._redirect_uri = config.spotify_redirect_uri.get_secret_value()
        self._spotify_search_client = spotipy.Spotify(client_credentials_manager=
                                                      SpotifyClientCredentials(client_id=self._client_id,
                                                                               client_secret=self._client_secret))
        self._spotify_read_playback_state = spotipy.Spotify(auth_manager=
                                                            SpotifyOAuth(scope="user-read-playback-state",
                                                                         client_id=self._client_id,
                                                                         client_secret=self._client_secret,
                                                                         redirect_uri=self._redirect_uri))
        self._spotify_modify_state_client = spotipy.Spotify(auth_manager=
                                                            SpotifyOAuth(scope="user-modify-playback-state",
                                                                         client_id=self._client_id,
                                                                         client_secret=self._client_secret,
                                                                         redirect_uri=self._redirect_uri))
        self._playback = self._spotify_read_playback_state.current_playback()
        self._last_playback_update: time = time.time()
        self._playing = self._is_playing()

    @staticmethod
    def __get_info(item) -> list[list[str]]:
        """
        collects artist, track, uri from search request and pack to list
        :param item:
        :return: list of lists of artist, track, uri
        """
        res = []
        for i in item["tracks"]["items"]:
            res.append([i["artists"][0]["name"], i["name"], i["uri"]])
        return res

    @staticmethod
    def get_raw_iru(uri: str):
        return uri[uri.rfind(":") + 1:]

    @staticmethod
    def get_full_uri(uri: str):
        if uri.find(Spotify._prefix) == -1:
            return Spotify._prefix + uri

    async def force_update_playback(self):
        """
        updates playback client
        :return:
        """
        self._playback = self._spotify_read_playback_state.current_playback()
        self._last_playback_update = time.time()

    async def _update_playback(self):
        time_passed = time.time() - self._last_playback_update
        if time_passed >= self._update_seconds:
            await self.force_update_playback()

    def _is_playing(self):
        return self._playback["is_playing"]

    async def get_curr_track_name(self):
        await self._update_playback()
        if self._playback is not None:
            return self._playback["item"]["name"]
        else:
            return None

    async def get_curr_track_artists(self):
        await self._update_playback()
        if self._playback is not None:
            artists = [artist["name"] for artist in self._playback["item"]["artists"]]
            return artists
        else:
            return None

    async def get_curr_track(self, separator=' - '):
        await self._update_playback()
        if self._playback is not None:
            return ', '.join([artist["name"] for artist in self._playback["item"]["artists"]]) + separator + self._playback["item"]["name"]
        else:
            return None

    def add_track_to_queue(self, uri: str):
        self._spotify_modify_state_client.add_to_queue(uri)

    async def next_track(self):
        self._spotify_modify_state_client.next_track()
        await asyncio.sleep(self._force_update_timeout)
        await self.force_update_playback()

    async def previous_track(self):
        self._spotify_modify_state_client.previous_track()
        await asyncio.sleep(self._force_update_timeout)
        await self.force_update_playback()

    async def start_pause(self):
        if self._playing:
            self._spotify_modify_state_client.pause_playback()
        else:
            self._spotify_modify_state_client.start_playback()
        self._playing = not self._playing

    def search(self, request: str) -> list[list[str]]:
        """
        :param request: запрос
        :return: список с автором, названием
        """

        return self.__get_info(self._spotify_search_client.search(request))


class AsyncSpotify:

    _prefix = 'spotify%3Atrack%3A'

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

        self._session = asyncspotify.Client(self._auth)

    async def authorize(self):
        await self._session.authorize()
        try:
            await self._session.player_currently_playing()
        except asyncspotify.exceptions.NotFound:
            raise ConnectionError("there is no active device")

    async def close(self):
        await self._session.close()

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
            currently_playing = await self._session.player_currently_playing()
            if currently_playing.is_playing:
                curr_track = currently_playing.track
                artists = [artist.name for artist in curr_track.artists]
                name = curr_track.name
                return [artists, name]
            else:
                return None
        except:
            raise ConnectionError

    async def add_track_to_queue(self, uri):
        try:
            await self._session.player_add_to_queue(uri)
        except:
            raise ConnectionError

    async def next_track(self):
        try:
            await self._session.player_next()
        except:
            raise ConnectionError

    async def previous_track(self):
        try:
            await self._session.player_prev()
        except:
            raise ConnectionError

    async def start_pause(self):
        try:
            currently_playing = await self._session.player_currently_playing()
            if currently_playing.is_playing:
                await self._session.player_pause()
            else:
                await self._session.player_play()
        except:
            raise ConnectionError

    async def search(self, request: str) -> list[list[str]]:
        """
        :param request: запрос
        :return: список с id, автором, названием
        """
        try:
            return await self.__get_info(await self._session.search("track", q=request, limit=10))
        except:
            raise ConnectionError

spotify = None
