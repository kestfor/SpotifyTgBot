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

    def find(self, artist: str, name: str) -> Lyrics:
        try:
            song = self._genius_api.search_song(title=name, artist=artist, get_full_info=False)
        except:
            raise ValueError("lyrics not found")
        else:
            raw_lyrics: str = song.lyrics
            last_non_digit = raw_lyrics.rfind("Embed") - 1 if raw_lyrics.rfind("Embed") != -1 else len(raw_lyrics) - 1
            for i in range(last_non_digit, -1, -1):
                if not raw_lyrics[i].isdigit():
                    last_non_digit = i
                    break
            lyrics = raw_lyrics[raw_lyrics.find("\n") + 1:last_non_digit + 1]
            return Lyrics(name, artist, lyrics)


if __name__ == '__main__':
    l = LyricsFinder()
    song = l.find("annihilate", "metro boomin")
    print(song.lyrics)