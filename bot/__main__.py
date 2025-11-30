from . import client, settings

async def main():

  await client.start(bot_token = settings.tg_bot_token)
  await client.run_until_disconnected()


if __name__ == "__main__":
  client.loop.run_until_complete(main())
