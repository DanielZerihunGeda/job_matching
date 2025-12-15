from . import client, cli, settings
import asyncio



async def main():

  await client.start(bot_token = settings.tg_bot_token)
  
  
  await cli.start()
  await asyncio.gather(
        client.run_until_disconnected(),
        cli.run_until_disconnected()
    )

if __name__ == "__main__":
  asyncio.run(main())
  
