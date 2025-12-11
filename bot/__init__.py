from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events
from .tools import pdf_loader
from io import BytesIO


class Settings(BaseSettings):

  tg_api_id: int
  tg_api_hash: str
  tg_bot_token: str

  model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8',
   extra = 'allow')


settings = Settings()
client = TelegramClient('bot', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)


@client.on(events.NewMessage)

async def handler(event):

  if event.media:
    
    f_name = event.message.file.name
    
    print("######### Downloading the file bytes")
    raw_f = await event.download_media(bytes)
    print(f"\n\n######## file downloaded \n\n")
    
    print(f"#### Loading the Document ........\n\n")
    parsed_t = pdf_loader(f_name, raw_f)
    
    print(f"######### Document Parsed Successfully \n\n")
    await event.reply(f"Documt name : {f_name}")


