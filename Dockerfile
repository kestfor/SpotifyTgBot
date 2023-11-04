FROM python:3.10-alpine
COPY requirements.txt requirements.txt
RUN pip install --upgrade --prefer-binary --no-cache-dir -r requirements.txt
WORKDIR /bots/SpotifyBot
COPY . .