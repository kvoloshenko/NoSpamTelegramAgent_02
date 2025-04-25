import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
# from spam_agent import agent_check_spam
from spam_agent_langgraph_02 import agent_check_spam
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        logger.info(f"Получено сообщение без текста (тип: {message.content_type})")
        return  # Пропускаем обработку

    logger.info(f"Проверка сообщения: {message.text[:50]}...")
    await agent_check_spam(message)


async def main():
    logger.info("Запуск бота...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал на завершение работы")
    finally:
        logger.info("Программа завершена")