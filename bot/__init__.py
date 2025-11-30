from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events

class Settings(BaseSettings):

  tg_api_id: int
  tg_api_hash: str
  tg_bot_token: str

  model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')


settings = Settings()
client = TelegramClient('bot', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)


@client.on(events.NewMessage)

async def handler(event):

  if event.media:
    await event.reply("This is Document")


