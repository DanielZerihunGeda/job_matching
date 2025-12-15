from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events
from .tools import pdf_loader, embed, Qdrant
from io import BytesIO


class Settings(BaseSettings):

  tg_api_id: int
  tg_api_hash: str
  tg_bot_token: str

  model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8',
   extra = 'allow')


settings = Settings()
client = TelegramClient('bot', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)

cli = TelegramClient('me', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)

q_client = Qdrant(settings.q_url, settings.q_api_key)


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
    
    print("######## Embedding the text >>>>>>>")
    embedding = embed(parsed_t)
    print("####### Embedded successfully")
    #print(f'embedding \n: {embedding.tolist()}')
    
    print(f"upserting to {event.sender_id} >>>>>>>>")
    
    res = q_client.upsert(embedding, event.sender_id)
    
    if res:
        print(f"upserted successfully")
    
    else:
        print("user already existed")
    await event.reply(f"Documt name : \n\n{parsed_t[:20]}\n")
    
    mes = await cli.get_messages(entity = 'ch_link', limit=1)
    
    print(f"mes: {mes[0].message}")


