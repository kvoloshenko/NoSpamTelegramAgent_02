import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
from agents import Agent
from tools import create_tools
from spam_storage import save_spam_message

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация инструментов с зависимостями
tools = create_tools(bot, TARGET_GROUP_ID)

# Конфигурация AI Agent
# assistant = AssistantClient(
assistant = Agent(
    name="AntiSpamAgent",
    instructions="""
    Ты - продвинутый анти-спам бот для Telegram. Анализируй сообщения по следующим критериям:
    1. Призывы к личным сообщениям
    2. Финансовые схемы
    3. Подозрительные ссылки
    4. Неестественный язык

    При обнаружении спама:
    1. Сохрани запись через save_spam
    2. Удали сообщение через delete_message
    3. Перешли сообщение модераторам через forward_message
    4. Заблокируй пользователя через block_user

    Формат ответа: только вызов инструментов
    """,
    tools=tools,
    model="gpt-4-turbo",
    api_key=OPENAI_API_KEY
)


@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return

    context = {
        "user_id": message.from_user.id,
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "sender_name": message.from_user.full_name,
        "message_text": message.text
    }

    prompt = f"""
    [Контекст]
    User ID: {context['user_id']}
    Chat ID: {context['chat_id']}
    Message ID: {context['message_id']}
    Sender: {context['sender_name']}

    [Сообщение]
    {context['message_text']}
    """

    try:
        session = assistant.new_session()
        await session.respond(prompt)
    except Exception as e:
        logger.error(f"Agent error: {e}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())