import asyncio
from config_reader import config
from aiogram import Bot, Dispatcher
from handlers import router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from data_base import db


async def main():
    token = config.bot_token.get_secret_value()
    bot = Bot(token=token)
    dp = Dispatcher()
    scheduler = AsyncIOScheduler()
    db.add_scheduler(scheduler)
    scheduler.start()
    dp.include_routers(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
