import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import API_TOKEN
from database import init_db
from handlers import router
from scheduler import check_time_loop, send_startup_notifications

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    await init_db()
    await send_startup_notifications(bot)
    asyncio.create_task(check_time_loop(bot))
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
