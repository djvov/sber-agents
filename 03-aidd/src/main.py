import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Регистрация обработчиков
    from src.bot import register_handlers
    register_handlers(dp)

    # Запуск polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



