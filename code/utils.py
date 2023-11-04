import random
import json
from string import ascii_letters


def generate_token(length) -> str:
    token = ''.join([random.choice(ascii_letters) for _ in range(length)])
    return token


def update_admins(user_id, user_name):
    with open("../data/admins.json", 'r', encoding="utf-8") as file:
        before = json.load(file)
    before[user_id] = user_name
    with open('../data/admins.json', 'w', encoding="utf-8") as file:
        file.write(json.dumps(before, indent=4, ensure_ascii=False))
