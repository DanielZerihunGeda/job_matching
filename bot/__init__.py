from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient, events
from .tools import pdf_loader, embed
from io import BytesIO
from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError
from pydantic import BaseModel, Field
import asyncpg
import uuid 
import asyncio
import logging
from telethon import functions, types


logger = logging.getLogger('Job_Scrapping')
logger.setLevel(logging.DEBUG)

if not logger.handlers:

    #Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    #File Handler
    fh = logging.FileHandler('job_scrapping.log', mode = 'w', encoding = 'utf-8', delay = True)
    fh.setLevel(logging.DEBUG)

    ft = logging.Formatter('%(asctime)s - %(name)s - %(message)s')

    ch.setFormatter(ft)
    fh.setFormatter(ft)

    logger.addHandler(ch)
    logger.addHandler(fh)


JOB_LISTS = ['Economics', 'Sociology', 'Physics', 'Chemistry', 'Biology', 'Geology', 'Political Science', 'Civil Engineering', 'Mechanical Engineering', 'Chemical Engineering', 'Food Engineering' 'Construction Technology Management', 'Computer Engineering', 'Biomedical Engineering', 'Computer Science', 'Information Technology', 'Software Engineering', 'Cybersecurity', 'Data Science', 'Artificial Intelligence', 'Accounting', 'Marketing', 'Business Management', 'Graphics Designer']

CH = ['hahujobsforfreshgraduates', 'freelance_ethio', 'harmeejobs', 
      'hahujobs', 'ethiojobsofficial', 'effoyjobs', 'geezjobs_ethiopia',
      'jobs_in_ethio', ]

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

async def get_llm_response(system_prompt: str, user_prompt: str, *args) -> list | None:
    """
    Get parsed job titles from LLM based on system and user prompts.
    
    Args:
        system_prompt (str): The system instruction for the LLM.
        user_prompt (str): The user's input parsed from resume.
    
    Returns:
        str | None: Comma-separated job titles if successful, None otherwise.
    """
    # Validate inputs
    if not system_prompt or not user_prompt:
        logger.debug("Missing system_prompt or user_prompt")
        return None

    try:
        _llm_client = await llm_client()
        
        res = await _llm_client.responses.parse(
            model=MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            # top_p=0.85,
            text_format=FieldValidator,
        )
        
        if not res or not hasattr(res, 'output_parsed') or not res.output_parsed:
            logger.debug("LLM returned empty or invalid parsed response")
            return None
        
        result = res.output_parsed.job_title
        
        if not result:
            logger.debug("No job titles extracted by LLM")
            return None
            
        logger.info(f"LLM extracted job titles: {','.join(result)}")
        return result
        
    except RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        return None
    except APIConnectionError as e:
        logger.error(f"Connection error to API: {e}")
        return None
    except APIError as e:
        logger.error(f"API error: {e}")
        return None
    except BadRequestError as e:
        logger.error(f"Bad request: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error in : {e}")
        return None


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
    if int(event.sender_id) in [int(settings.account_id) , int(settings.account_id_o)]:
        logger.info('Self account message ignored')
        return

    if not event.media:
        logger.info(f"Message has no media ignoring\n\nSender_id: {event.sender_id}\n\n")
        await event.reply('Please upload or update your resume maxsize = 5mb')
        return
    # Get file name and download
    f_name = event.message.file.name or "unknown_file.pdf"
    logger.info(f"File uploaded: {f_name}")
    file_size = event.message.file.size #getting file size
    
    if file_size >=5*(10**6):
        logger.info(f'File size exceed maxsize: sent from user_id: {event.sender_id} filesize: {file_size}')
        await event.reply('You are allowed to upload max size of 5mb document')
        return
    raw_f = await event.download_media(bytes)
    if not raw_f:
        logger.warning("Failed to download file")
        return

    logger.info("File download completed")

    # Parse PDF
    byte_fi, parsed_t = pdf_loader(f_name, raw_f)

    if not parsed_t:
        logger.info("File parsing failed or returned empty text")
        return

    logger.info("File parsed successfully")

    # Prepare prompts for LLM
    system_prompt = f"""
        You are an expert in analyzing candidate resumes and extracting the most suitable job titles.
        Your task:
        - Carefully analyze the candidate's skills, education, work experience, and achievements.
        - From the provided list of job titles ONLY, select one or more that best match the candidate's profile.
        - Do NOT make up or suggest any job title not in the list.
        Available Job Titles:
        **{' | '.join(JOB_LISTS)}**
            """.strip()
            
    user_prompt = parsed_t

    res = await get_llm_response(system_prompt, user_prompt)
    
    if not res:
        logger.warning("LLM failed to return valid job titles")
        await event.reply("Sorry, I couldn't determine suitable job titles from your resume. Please try again.")
        return
        
    result = ','.join(res)
    logger.info(f"Extracted job titles: {result}")
    
    try:
        if pgpool is None:
            await get_pool()
        
        async with pgpool.acquire() as conn:
            logger.info("Postgres connected successfully")

            # Create table if not exists
            create_table_query = """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id BIGINT UNIQUE NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    raw_file BYTEA
                );
            """
            await conn.execute(create_table_query)

            # Upsert user data
            user_id = int(event.sender_id)
            upsert_query = """
                INSERT INTO users (user_id, title)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                SET title = EXCLUDED.title;
            """
            await conn.execute(upsert_query, user_id, result)
            logger.info(f"User {user_id} information upserted successfully with titles: {res}")
            await event.reply(f"Thanks! I've analyzed your resume.\n\nBest matching job titles:\n**{result.replace(',', ' | ')}** \n\nYou will be notified, If you meet the requirements")

    except asyncpg.ClientConfigurationError as e:
        logger.error(f"client config error occured from {event.sender_id}: {e}")
        await event.reply("An error occurred while saving in Database.")
    except asyncpg.PostgresError as e:
        logger.error(f"Postgres error occured from :{event.sender_id}: {e}")
    except asyncpg.InternalClientError as e:
        logger.error(f"Internal client error from: {event.sender_id}: {e}")
    except Exception as e:
        logger.error(f"Unknown error from: {event.sender_id}: {e}")
                
@cli.on(events.NewMessage(chats = CH, incoming = True))
async  def forward_message(event):
    logger.info(f"new event has arrived from {event.sender_id}")

    try:
        await cli.forward_messages('testlenj', event.message)
        logger.info(f'forwarded to testlenj')
    except Exception as e:
        logger.error(f"Failed to forward message from {event.sender_id}: {e}")
    
      
@client.on(events.NewMessage(chats=['testlenj'], incoming = True))
async def analyzer(event):

    logger.info(f"new event has arrived from {event.sender_id}")
    system_message = f'''
                    You are a precise job matching assistant.

                    Your task:
                    - Analyze the required skills, qualifications, experience, and responsibilities in the job description.
                    - From the list below ONLY, select one or more job titles that best fit this role.
                    - Do NOT create or suggest any job title not in the list.
                    - Return only the matching titles.

                    Available Job Titles:
                    **{" | ".join(JOB_LISTS)}**
                        '''.strip()
    job_description = event.message.message
    user_message = f"Job Description:\n\n{job_description}"
    
    res = await get_llm_response(system_message, user_message)
    if not res:
        logger.warning('llm failed to parse appropriate job title from the job description')

        del_mes = await cli(functions.channels.DeleteMessagesRequest(
                channel = 'testlenj',
                id = [event.message.id]
            ))

        logger.info(f"Message deleted from testlenj channel: {del_mes.stringify()}")
        return
        
    job_title_li = res
    job_title_li = [title.strip() for title in job_title_li if title and title.strip()]
    
    if not job_title_li:
        logger.warning("Empty job title list after cleaning")
        return
    
    logger.info(f"Job title is extracted from job description Job Title : {','.join(res)}")
    
    try:
        logger.info("Matching User with job descriptions")
        if pgpool is None:
            await get_pool()
        async with pgpool.acquire() as conn:
            res = await conn.fetch("""
                    SELECT user_id 
                    FROM users 
                    WHERE string_to_array(title, ',') && $1;
                """, job_title_li)
        fetched_li = [dict(r) for r in res]
        logger.info("Matching Completed")
        if fetched_li:
            for user_dict in fetched_li:
                user_id = user_dict['user_id']
                try:
                    await client.forward_messages(user_id, event.message)
                    logger.info(f'forwarded to client {user_id}')
                    await asyncio.sleep(3)
                
                except Exception as e:
                    logger.warning(f'Failed to send to user {user_id}: {e}')

            #Deleting messages from intermediate channel

        else:
            logger.info("No matching users found in database")
        
        del_mes = await cli(functions.channels.DeleteMessagesRequest(
                channel = 'testlenj',
                id = [event.message.id]
            ))

        logger.info(f"Message deleted from testlenj channel: {del_mes.stringify()}")
            
    except Exception as e:
        logger.error(f"Error fetching from the database for Job Title: {','.join(job_title_li)}")
