from . import client, cli, settings, logger
import asyncio
from telethon import events
import subprocess



received_code = None
code_event = asyncio.Event()
phone_code_hash = None

@client.on(events.NewMessage(chats=['tggcodd'], incoming=True))
async def catch_verification_code(event):
    #checking session file at first execution:
        
    global received_code
    print(event.message.text)
    if event.message.text and event.message.text.isdigit():
        received_code = event.message.text.strip()
        code_event.set()
        await event.reply("Code received! Logging in...")

async def get_verification_code():
    global received_code
    await code_event.wait()
    code = received_code
    received_code = None
    code_event.clear()
    return code

async def main():
    await client.start(bot_token=settings.tg_bot_token)
    
    if not cli.is_connected():
        try:
            await cli.connect()
        except OSError as e:
            logger.error(f'User client failed to connect: {e}')
            return
    
    
    global phone_code_hash
    try:
        sent_code = await cli.send_code_request(settings.phone)
        phone_code_hash = sent_code.phone_code_hash
        logger.info('Verification code sent. Waiting for code ...')
    except Exception as e:
        logger.error(f'Failed to send verification code: {e}')
        return
    
    try:
        code = await asyncio.wait_for(get_verification_code(), timeout=300)  # Add 5-min timeout to prevent hangs
        logger.info('code received')
    except asyncio.TimeoutError:
        logger.error('verification timeout')
        return
    
    try:
        await cli.sign_in(settings.phone, code, phone_code_hash=phone_code_hash)
        logger.info('login successful!')
    except Exception as e:
        logger.error(f'error verifying code: {e}')
        return
    
    logger.info('clients are running successfully')
    await asyncio.gather(
        client.run_until_disconnected(),
        cli.run_until_disconnected()
    )

if __name__ == "__main__":
    asyncio.run(main())
