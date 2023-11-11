class SpotifyErrors(Exception):
    def __init__(self, message=''):
        self.message = message


class PremiumRequired(SpotifyErrors):
    """
    current user hasn't got spotify premium
    """
    pass


class ConnectionError(SpotifyErrors):
    pass

