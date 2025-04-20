from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, function_tool
import os
from dotenv import load_dotenv
from spam_storage import save_spam_message
from dataclasses import dataclass
from typing import Any, List
import asyncio

os.environ["OPENAI_API_KEY"] = "No Need"
load_dotenv()


@dataclass
class MessageContext:
    sender_full_name: str
    message_text: str


LOCAL_LLM = os.getenv('LOCAL_LLM')
print(f'LOCAL_LLM = {LOCAL_LLM}')

model = OpenAIChatCompletionsModel(
    model=LOCAL_LLM,
    openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1")
)


@function_tool
async def save_spam(sender_name: str, message: str) -> dict:
    """Сохраняет спам-сообщение в базу данных"""
    try:
        save_spam_message(sender_name, message)
        print(f"Сохранён спам от {sender_name}: {message[:50]}...")
        return {"status": "success"}
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return {"status": "error", "details": str(e)}


instructions = """Ты — высокоточная система детекции спама для Telegram. Анализируй сообщения строго по нижеуказанным правилам.

### Критерии СПАМА (отвечать "SPAM"):
1. **Финансовые обещания**
2. **Скрытое взаимодействие**
3. **Расплывчатые предложения**
4. **Структурные маркеры**

### Исключения (отвечать "NOT_SPAM"):
1. **Техническая лексика**
2. **Нормальная коммуникация**

### Правила обработки:
1. Формат ответа: ТОЛЬКО "SPAM" или "NOT_SPAM"
2. При спаме ВСЕГДА вызывай save_spam с параметрами:
   - sender_name = полное имя отправителя из контекста
   - message = полный текст сообщения
3. Никаких дополнительных комментариев
"""


class SpamDetectionAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_context: MessageContext = None

    async def run(self, inputs: List[Any]) -> Any:
        # Получаем контекст из первого элемента ввода
        self.current_context = inputs[0]
        return await super().run([self.current_context.message_text])

    @function_tool
    async def context_aware_save_spam(self) -> dict:
        """Враппер для сохранения спама с использованием контекста"""
        return await save_spam(
            sender_name=self.current_context.sender_full_name,
            message=self.current_context.message_text
        )


# Инициализация агента с инструментами
agent = SpamDetectionAgent(
    name="AdvancedSpamDetector",
    instructions=instructions,
    tools=[save_spam],  # Можно заменить на context_aware_save_spam при необходимости
    model=model
)

# Пример использования
if __name__ == "__main__":
    # Создаём контекст сообщения
    test_context = MessageContext(
        sender_full_name="Иван Иванов",
        message_text="Зарабатывайте 500$ в день! Напишите мне в личные сообщения для деталей."
    )

    # Запускаем обработку
    try:
        result = Runner.run_sync(agent, [test_context])
        print(f"Результат: {result.final_output}")
    except Exception as e:
        print(f"Ошибка выполнения: {e}")