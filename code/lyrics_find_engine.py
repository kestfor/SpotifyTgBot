import lyricsgenius
from lyricsgenius.utils import clean_str
from bs4 import BeautifulSoup
import re


class Genius(lyricsgenius.Genius):
    """User-level interface with the Genius.com API and public API.

        Args:
            access_token (:obj:`str`, optional): API key provided by Genius.
            response_format (:obj:`str`, optional): API response format (dom, plain, html).
            timeout (:obj:`int`, optional): time before quitting on response (seconds).
            sleep_time (:obj:`str`, optional): time to wait between requests.
            verbose (:obj:`bool`, optional): Turn printed messages on or off.
            remove_section_headers (:obj:`bool`, optional): If `True`, removes [Chorus],
                [Bridge], etc. headers from lyrics.
            skip_non_songs (:obj:`bool`, optional): If `True`, attempts to
                skip non-songs (e.g. track listings).
            excluded_terms (:obj:`list`, optional): extra terms for flagging results
                as non-lyrics.
            replace_default_terms (:obj:`list`, optional): if True, replaces default
                excluded terms with user's. Default excluded terms are listed below.
            retries (:obj:`int`, optional): Number of retries in case of timeouts and
                errors with a >= 500 response code. By default, requests are only made once.

        Attributes:
            verbose (:obj:`bool`, optional): Turn printed messages on or off.
            remove_section_headers (:obj:`bool`, optional): If `True`, removes [Chorus],
                [Bridge], etc. headers from lyrics.
            skip_non_songs (:obj:`bool`, optional): If `True`, attempts to
                skip non-songs (e.g. track listings).
            excluded_terms (:obj:`list`, optional): extra terms for flagging results
                as non-lyrics.
            replace_default_terms (:obj:`list`, optional): if True, replaces default
                excluded terms with user's.
            retries (:obj:`int`, optional): Number of retries in case of timeouts and
                errors with a >= 500 response code. By default, requests are only made once.

        Returns:
            :class:`Genius`

        Note:
            Default excluded terms are the following regular expressions:
            :obj:`track\\s?list`, :obj:`album art(work)?`, :obj:`liner notes`,
            :obj:`booklet`, :obj:`credits`, :obj:`interview`, :obj:`skit`,
            :obj:`instrumental`, and :obj:`setlist`.

        """

    def __init__(self, access_token=None,
                 response_format='plain', timeout=5, sleep_time=0.2,
                 verbose=True, remove_section_headers=False,
                 skip_non_songs=True, excluded_terms=None,
                 replace_default_terms=False,
                 retries=0,
                 ):
        if access_token is None:
            access_token = "pass"
        super().__init__(access_token=access_token, response_format=response_format, timeout=timeout,
                         sleep_time=sleep_time, verbose=verbose, remove_section_headers=remove_section_headers,
                         skip_non_songs=skip_non_songs, excluded_terms=excluded_terms,
                         replace_default_terms=replace_default_terms,
                         retries=retries
                         )

    def lyrics(self, song_id=None, song_url=None, remove_section_headers=False):
        """Uses BeautifulSoup to scrape song info off of a Genius song URL

        You must supply either `song_id` or song_url`.

        Args:
            song_id (:obj:`int`, optional): Song ID.
            song_url (:obj:`str`, optional): Song URL.
            remove_section_headers (:obj:`bool`, optional):
                If `True`, removes [Chorus], [Bridge], etc. headers from lyrics.

        Returns:
            :obj:`str` \\|‌ :obj:`None`:
                :obj:`str` If it can find the lyrics, otherwise `None`

        Note:
            If you pass a song ID, the method will have to make an extra request
            to obtain the song's URL and scrape the lyrics off of it. So it's best
            to pass the method the song's URL if it's available.

            If you want to get a song's lyrics by searching for it,
            use :meth:`Genius.search_song` instead.

        Note:
            This method removes the song headers based on the value of the
            :attr:`Genius.remove_section_headers` attribute.

        """
        msg = "You must supply either `song_id` or `song_url`."
        assert any([song_id, song_url]), msg
        if song_url:
            path = song_url.replace("https://genius.com/", "")
        else:
            path = self.song(song_id)['song']['path'][1:]

        # Scrape the song lyrics from the HTML
        html = BeautifulSoup(
            self._make_request(path, web=True).replace('<br/>', '\n'),
            "lxml"
        )

        # Determine the class of the div
        div = html.find("div", class_=re.compile("^lyrics$|Lyrics__Root"))
        if div is None:
            if self.verbose:
                print("Couldn't find the lyrics section. "
                      "Please report this if the song has lyrics.\n"
                      "Song URL: https://genius.com/{}".format(path))
            return None

        lyrics = div.get_text()

        # Remove [Verse], [Bridge], etc.
        if self.remove_section_headers or remove_section_headers:
            lyrics = re.sub(r'(\[.*?\])*', '', lyrics)
            lyrics = re.sub('\n{2}', '\n', lyrics)  # Gaps between verses
        return lyrics.strip("\n")

    def _get_item_from_search_response(self, response, search_term, type_, result_type):
        """Gets the desired item from the search results.

        This method tries to match the `hits` of the :obj:`response` to
        the :obj:`response_term`, and if it finds no match, returns the first
        appropriate hit if there are any.

        Args:
            response (:obj:`dict`): A response from
                :meth:‍‍‍‍`Genius.search_all` to go through.
            search_term (:obj:`str`): The search term to match with the hit.
            type_ (:obj:`str`): Type of the hit we're looking for (e.g. song, artist).
            result_type (:obj:`str`): The part of the hit we want to match
                (e.g. song title, artist's name).

        Returns:
            :obj:‍‍`str` \\|‌ :obj:`None`:
            - `None` if there is no hit in the :obj:`response`.
            - The matched result if matching succeeds.
            - The first hit if the matching fails.

        """

        # Convert list to dictionary
        top_hits = response['sections'][0]['hits']

        # Check rest of results if top hit wasn't the search type
        sections = sorted(response['sections'],
                          key=lambda sect: sect['type'] == type_)

        hits = [hit for hit in top_hits if hit['type'] == type_]
        hits.extend([hit for section in sections
                     for hit in section['hits']
                     if hit['type'] == type_])

        best_match = None
        for hit in hits:
            item = hit['result']
            if clean_str(search_term) in clean_str(item[result_type]):
                if best_match is None or len(clean_str(item[result_type])) < len(best_match[result_type]):
                    best_match = item
        if best_match is not None:
            return best_match

        # If the desired type is song lyrics and none of the results matched,
        # return the first result that has lyrics
        if type_ == 'song' and self.skip_non_songs:
            for hit in hits:
                song = hit['result']
                if self._result_is_lyrics(song):
                    return song

        return hits[0]['result'] if hits else None

    def search_song(self, title=None, artist="", song_id=None,
                    get_full_info=True):
        return super().search_song(title, artist, song_id, get_full_info)

