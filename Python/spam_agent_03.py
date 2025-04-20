from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, function_tool
import os
from dotenv import load_dotenv
from spam_storage import save_spam_message
from typing import Any, Dict, List  # Добавили импорт List
import asyncio

os.environ["OPENAI_API_KEY"] = "No Need"
load_dotenv()

LOCAL_LLM = os.getenv('LOCAL_LLM')
print(f'LOCAL_LLM = {LOCAL_LLM}')

model = OpenAIChatCompletionsModel(
    model=LOCAL_LLM,
    openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1")
)


@function_tool
async def save_spam(sender_name: str, message_text: str) -> Dict:
    """Сохраняет спам-сообщение с указанным отправителем и текстом"""
    try:
        save_spam_message(sender_name, message_text)
        print(f"Сохранён спам от {sender_name}")
        return {"status": "success"}
    except Exception as e:
        print(f"Ошибка: {str(e)}")
        return {"status": "error", "details": str(e)}


instructions = """Ты — система детекции спама. Анализируй сообщения по правилам:

1. Определи SPAM/NOT_SPAM
2. Для SPAM всегда вызывай save_spam с параметрами:
   - sender_name = имя отправителя из контекста
   - message_text = полный текст сообщения

Формат ответа: только "SPAM" или "NOT_SPAM"
"""


class SpamAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context: Dict[str, str] = {}

    async def run(self, inputs: List[Any]) -> Any:
        if inputs and isinstance(inputs[0], dict):
            self.context = inputs[0]
        return await super().run([self.context.get('message_text', '')])

    @function_tool
    async def save_spam_wrapper(self) -> Dict:
        return await save_spam(
            sender_name=self.context.get('sender_full_name', ''),
            message_text=self.context.get('message_text', '')
        )


# Инициализация агента
agent = SpamAgent(
    name="TelegramSpamDetector",
    instructions=instructions,
    tools=[save_spam],
    model=model
)

# Пример использования
if __name__ == "__main__":
    # Подготавливаем данные в виде словаря
    message_data = {
        "sender_full_name": "Иван Иванов",
        "message_text": "Зарабатывайте 500$ в день! Напишите мне в ЛС!"
    }

    # Передаем словарь напрямую
    try:
        result = Runner.run_sync(agent, message_data)
        print(f"Результат: {result.final_output}")
    except Exception as e:
        print(f"Ошибка: {str(e)}")