from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events
from .tools import pdf_loader, embed
from io import BytesIO
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
import asyncpg
import uuid 


JOB_LISTS = ['Economics', 'Sociology', 'Physics', 'Chemistry', 'Biology', 'Geology', 'Political Science', 'Civil Engineering', 'Mechanical Engineering', 'Chemical Engineering', 'Food Engineering' 'Construction Technology Management', 'Computer Engineering', 'Biomedical Engineering', 'Computer Science', 'Information Technology', 'Software Engineering', 'Cybersecurity', 'Data Science', 'Artificial Intelligence', 'Accounting', 'Marketing', 'Business Management', 'Graphics Designer']

MODEL = 'openai/gpt-oss-120b'

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


async def llm_client(api_key: str = settings.grok_api_key, base_url: str = 'https://api.groq.com/openai/v1') -> AsyncOpenAI:
    client = AsyncOpenAI(api_key = api_key, base_url = base_url)
    return client

pgpool = None


async def get_pool():
    global pgpool
    
    if not pgpool:
        pgpool = await asyncpg.create_pool(host = settings.host, 
                               port = settings.port,
                               user = settings.user,
                               database = settings.dbname,
                               password = settings.password)
                               
    return pgpool
    



@client.on(events.NewMessage)
async def handler(event):

  if event.media:
    
    f_name = event.message.file.name
    print("######### Downloading the file bytes")
    raw_f = await event.download_media(bytes)
    print(f"\n\n######## file downloaded \n\n")
    
    
    print(f"#### Loading the Document ........\n\n")
    byte_fi, parsed_t= pdf_loader(f_name, raw_f)
    
    
    print(f"######### Document Parsed Successfully \n\n")
    
    # Omit email contact addresses
    _llm_client = await llm_client()
    res = await _llm_client.responses.parse(
    model = MODEL
    ,
    
    input = [
        {"role": "system", "content": f"You are expert in analyzing and extracting users qualification/job_title for a candidate based on provided details about candidates information. First analyze the users skills, educational background and experiences, Then select one or more from the given list of job titles only don't assign job title by your own select the most appropriate from the job titles.\n Job Titles: \n **{' '.join(JOB_LISTS)}**"},
        {
            "role": "user",
            "content": f"{parsed_t}",
        },
    ],
    temperature = 0.2,
    #top_p = 0.85
    
    text_format = FieldValidator,
    )
    
    
    res = ','.join(res.output_parsed.job_title)
    
    if not res:
        return 
    pool = await get_pool()
    
    async with pool.acquire() as conn:
      print('postgres connected successfully')
      table_q = ''' CREATE TABLE IF NOT EXISTS users(
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id BIGINT UNIQUE NOT NULL,
                        title varchar(225) NOT NULL,
                        raw_file BYTEA
                        );'''
                        
      await conn.execute(table_q)
                    
      user_id = int(event.sender_id)
      
      upsert_q = '''INSERT INTO users (user_id, title)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO UPDATE
                    SET title = EXCLUDED.title;  
      '''
      
      await conn.execute(upsert_q, user_id, res) 
      
      rep = await conn.fetch("""SELECT user_id FROM users WHERE string_to_array(title, ',') && ARRAY['Data Science'];""")
      print(rep)
      
      

@cli.on(events.NewMessage(chats=['testlenj', 'SmsmaIo'], incoming = True))
async def analyzer(event):

    print("event is recieved")
    _llm_client = await llm_client()
    res = await _llm_client.responses.parse(
    
            model = MODEL,
            input = [
                    {
                            'role': 'system',
                            'content': f'''You are a helpful assistant. You will analyze required 
                            qualifications a job description then select one or more appropriate 
                            job title from the given list of job titles. Job Titles: \n\n **{" ".join(JOB_LISTS)}**'''  
                    },
                    
                    {
                            'role': 'system',
                            'content': f'Job Descriptions \n\n{event.message.message}'
                    }
            ],
            
            temperature = 0.2,
            text_format = FieldValidator
    )
    
    job_title_li = res.output_parsed.job_title
    
    print(job_title_li)
    pool = await get_pool()
    
    async with pool.acquire() as conn:
       res = await conn.fetch("""
            SELECT user_id 
            FROM users 
            WHERE string_to_array(title, ',') && $1;
        """, job_title_li)
       print(res)
    
    
    
