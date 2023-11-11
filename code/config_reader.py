from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    bot_token: SecretStr
    spotify_username: SecretStr
    spotify_client_id: SecretStr
    spotify_client_secret: SecretStr
    spotify_redirect_uri: SecretStr
    data_path: SecretStr
    token_file: SecretStr
    admin_file: SecretStr

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


config = Settings()
