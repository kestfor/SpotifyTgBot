import asyncio
import threading

import lyrics_find_engine


class Lyrics:
    def __init__(self, name=None, artist=None, lyrics=None):
        self._name = name
        self._artist = artist
        self._lyrics = lyrics
        self._split_lyrics = lyrics.split('\n')
        for i in range(len(self._split_lyrics)):
            if 'You might also like' in self._split_lyrics[i]:
                self._split_lyrics[i] = self._split_lyrics[i][19:]
                self._lyrics = '\n'.join(self._split_lyrics)
                break

    def __bool__(self):
        return self._name is not None and self._artist is not None and self._lyrics is not None

    @property
    def name(self):
        return self._name

    @property
    def artist(self):
        return self._artist

    @property
    def lyrics(self):
        return self._lyrics

    @property
    def list_lyrics(self):
        return self._split_lyrics


class LyricsFinder:

    def __init__(self):
        self._genius_api = lyrics_find_engine.Genius(verbose=False, remove_section_headers=True)
        self._found_res = None

    def _api_request(self, title, artist):
        try:
            self._found_res = self._genius_api.search_song(title=title, artist=artist, get_full_info=False)
        except:
            self._found_res = ""

    async def find(self, artist: str, name: str) -> Lyrics:
        try:
            self._found_res = None
            thread = threading.Thread(target=self._api_request, args=(name, artist,))
            thread.start()
            while self._found_res is None:
                await asyncio.sleep(0.5)

            if self._found_res == "":
                raise Exception("No song name found")
        except:
            raise ValueError("lyrics not found")
        else:
            song = self._found_res
            raw_lyrics: str = song.lyrics
            last_non_digit = raw_lyrics.rfind("Embed") - 1 if raw_lyrics.rfind("Embed") != -1 else len(raw_lyrics) - 1
            for i in range(last_non_digit, -1, -1):
                if not raw_lyrics[i].isdigit():
                    last_non_digit = i
                    break
            lyrics = raw_lyrics[raw_lyrics.find("\n") + 1:last_non_digit + 1]
            return Lyrics(name, artist, lyrics)


async def test():
    l = LyricsFinder()
    song = await l.find("annihilate", "metro boomin")
    print(song.lyrics)


if __name__ == '__main__':
    asyncio.run(test())
