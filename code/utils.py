import random
from string import ascii_letters


def generate_token(length) -> str:
    token = ''.join([random.choice(ascii_letters) for _ in range(length)])
    return token
