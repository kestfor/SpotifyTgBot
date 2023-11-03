import random
from string import ascii_letters
import requests
from config_reader import config


def generate_token(length) -> str:
    token = ''.join([random.choice(ascii_letters) for _ in range(length)])
    return token
