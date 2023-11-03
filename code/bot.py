import asyncio
from config_reader import config
from aiogram import Bot, Dispatcher
from handlers import router


async def main():
    token = config.bot_token.get_secret_value()
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_routers(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
