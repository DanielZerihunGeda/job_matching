from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events
from .tools import pdf_loader, embed
from io import BytesIO
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
import asyncpg
import uuid 



class FieldValidator(BaseModel):

  job_title: list[str] = Field(..., json_schema_extra={
            "examples": [["Software Engineer", "Data Scientist"]]
        }
    )


class Settings(BaseSettings):

  tg_api_id: int
  tg_api_hash: str
  tg_bot_token: str
  grok_api_key: str

  model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8',
   extra = 'allow')


settings = Settings()

client = TelegramClient('bot', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)
cli = TelegramClient('me', api_id=settings.tg_api_id, api_hash=settings.tg_api_hash)

#Postgres url
postres_uri = f"postgresql://postgres:[{settings.postgres_password}]@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
llm_client = AsyncOpenAI(api_key = settings.grok_api_key, base_url='https://api.groq.com/openai/v1')

#q_client = Qdrant(settings.q_url, settings.q_api_key)


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
    
    #embedding = embed(parsed_t)
    
    #print(f'embedding \n: {embedding.tolist()}')
    
    
    
    '''
    
    res = q_client.upsert(embedding, event.sender_id)
    
    if res:
        print(f"upserted successfully")
    
    else:
        print("user already existed")
        
        '''
    # Omit email contact addresses
    res = await llm_client.responses.parse(
    model = 'openai/gpt-oss-120b',
    input = [
        {"role": "system", "content": f"You are expert in analyzing and extracting users qualification/job_title for a candidate based on provided details about user's data.First analyze the users skills, educational background and experiences, Then map them into an appropriate job title such as Accounting and Finance Manager, Electrical Engineer, Software Engineer, Machine Learning Engineer and etc, a single candidate can have multiple qualification so map each of them into the appropriate category."},
        {
            "role": "user",
            "content": f"{parsed_t}",
        },
    ],
    temperature = 0.2,
    #top_p = 0.85
    
    text_format = FieldValidator,
    )
    
    
    res = res.output_parsed
    
    if res:
        try:
            await conn = asyncpg.connect(postres_uri)
            
            print('postgres connected')
            query = f''' CREATE TABLE IF NOT EXISTS users(user_id)'''
            await conn.execute(
            '''query'''
            )
    
    await event.reply(f"\n\n{res}\n")
    
    
    
    #mes = await cli.get_messages(entity = 'ch_link', limit=1)
    
    #print(f"mes: {mes[0].message}")

@cli.on(events.NewMessage(chats=['SmsmaIo'], incoming = True))
async def analyzer(event):
    print("event is recieved")
    #await event.reply("Hello Dani what's up")
    await cli.send_message(entity = '@SmsmaIo', message = "message_recieved")


