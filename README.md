# NoSpamTelegram_02

## OpenAI Agents SDK Ollama
https://mer.vin/2025/03/openai-agents-sdk-ollama/

https://youtu.be/LYMwLixmTZQ?si=nAhJTWrHmhKb-Ar4

---
Для реализации анти-спам бота с использованием подхода AI Agents от OpenAI, мы переработаем структуру проекта, интегрировав Agents SDK. Вот обновленные модули:

**main.py**
```python
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
from openai.agents import AssistantClient
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
assistant = AssistantClient(
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
```

**tools.py**
```python
from aiogram import Bot
from openai.agents import tool
import logging

logger = logging.getLogger(__name__)

def create_tools(bot: Bot, target_group_id: str):
    @tool
    async def block_user(user_id: int, chat_id: int):
        """Блокирует пользователя. Параметры: user_id, chat_id"""
        try:
            await bot.ban_chat_member(chat_id, user_id)
            logger.info(f"Blocked user {user_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Block error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def delete_message(chat_id: int, message_id: int):
        """Удаляет сообщение. Параметры: chat_id, message_id"""
        try:
            await bot.delete_message(chat_id, message_id)
            logger.info(f"Deleted message {message_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def forward_message(chat_id: int, message_id: int):
        """Пересылает сообщение модераторам. Параметры: chat_id, message_id"""
        try:
            await bot.forward_message(
                chat_id=target_group_id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            logger.info(f"Forwarded message {message_id}")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return {"status": "error", "details": str(e)}

    @tool
    async def save_spam(sender_name: str, message_text: str):
        """Сохраняет спам в базу. Параметры: sender_name, message_text"""
        try:
            save_spam_message(sender_name, message_text)
            logger.info("Spam saved")
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Save error: {e}")
            return {"status": "error", "details": str(e)}

    return [block_user, delete_message, forward_message, save_spam]
```

**spam_storage.py** (без изменений)
```python
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def save_spam_message(sender_full_name: str, message_text: str):
    spam_data = {
        "timestamp": datetime.now().isoformat(),
        "sender": sender_full_name,
        "message": message_text
    }
    
    try:
        with open('spam_log.json', 'a') as f:
            json.dump(spam_data, f, ensure_ascii=False)
            f.write('\n')
        logger.info("Spam logged successfully")
    except Exception as e:
        logger.error(f"Logging failed: {e}")
```

**Требования (requirements.txt)**
```
aiogram>=3.0
python-dotenv>=0.19
openai-agents>=0.3
```

**Обновления в подходе:**
1. **Agents Core** - Централизованная логика обработки через AI Agent
2. **Инструменты как сервисы** - Каждое действие представлено автономным инструментом
3. **Контекстная обработка** - Агент получает полный контекст сообщения
4. **Сквозное логирование** - Детальное отслеживание всех операций
5. **Обработка ошибок** - Единый формат ответов от инструментов

Для работы необходимо:
1. Установить Agents SDK: `pip install openai-agents`
2. Добавить OPENAI_API_KEY в .env
3. Настроить модель GPT-4 через OpenAI API

Особенности реализации:
- Полная асинхронная обработка
- Автоматическое документирование инструментов
- Динамическое создание сессий для каждого сообщения
- Единая точка управления политиками модерации через промпт
