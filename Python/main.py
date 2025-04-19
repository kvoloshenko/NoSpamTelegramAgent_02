import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
from agents import Agent
from bot_tools import create_tools
from spam_storage import save_spam_message

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID')
# OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

LOCAL_LLM = os.getenv('LOCAL_LLM')
print(f'LOCAL_LLM ={LOCAL_LLM }')

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
    instructions="""Ты - продвинутый анти-спам бот для Telegram. 
Анализируй сообщения строго по нижеуказанным правилам.

### Критерии СПАМА (отвечать "SPAM"):
1. **Финансовые обещания**
   - Любые конкретные суммы ("350$", "от 500$", "2000$ в неделю")
   - Указание временного периода ("в день", "ежедневно", "за неделю")
   - Фразы: "доход от", "прибыль", "заработок", "получайте"

2. **Скрытое взаимодействие**
   - Прямые призывы: "пишите в ЛС", "в сообщения", "напишите мне"
   - Косвенные призывы: "заинтересованы?", "интересно?", "хотите узнать?"
   - Требование действий: "оставьте +", "напишите 'старт'"

3. **Расплывчатые предложения**
   - "Отличный формат", "интересное предложение", "выгодные условия"
   - "Сотрудничество", "удалённая работа" без конкретики
   - "Достойный доход", "хороший заработок" без деталей

4. **Структурные маркеры**
   - Сочетание финансовых цифр + вопроса + призыва к действию
   - Использование точек/тире вместо нормальных предложений

### Исключения (отвечать "NOT_SPAM"):
1. **Техническая лексика**
   - AI/ИИ, программирование (Python, C++), нейросети
   - Оборудование (GPU, CPU, сервера), фреймворки
   - Профессиональные термины ("инференс", "трансформер")

2. **Нормальная коммуникация**
   - Вопросы/обсуждения без финансового подтекста
   - Сообщения с конкретной технической информацией
   - Профессиональные дискуссии любого рода

### Особые указания:
1. Любое сочетание "конкретная сумма + призыв к действию" = SPAM
2. Технические термины перевешивают спам-маркеры
3. Короткие сообщения ("GPUStack") не считаются спамом

    При обнаружении спама:
    1. Сохрани запись через save_spam
    2. Перешли сообщение модераторам через forward_message
    3. Удали сообщение через delete_message

    Формат ответа: только вызов инструментов
    """,
    tools=tools,
    model=LOCAL_LLM,
    api_key="No Need"
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