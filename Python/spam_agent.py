from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    AsyncOpenAI,
    function_tool,
    RunContextWrapper,
    TResponseInputItem,
)
import os
import logging
from dataclasses import dataclass

from aiogram import types
from dotenv import load_dotenv

from spam_storage import save_spam_message

# ---------------------------------------------------------------------------
# 📦  Environment & logging setup
# ---------------------------------------------------------------------------
os.environ["OPENAI_API_KEY"] = "No Need"
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOCAL_LLM = os.getenv("LOCAL_LLM") or "llama3:latest"
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")

model = OpenAIChatCompletionsModel(
    model=LOCAL_LLM,
    openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1"),
)

# ---------------------------------------------------------------------------
# 🏷️  Context dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaskContext:
    """Быстрый контейнер для передачи данных между tool‑функциями."""

    sender_full_name: str
    target_group_id: str
    message_text: str
    message: types.Message


# ---------------------------------------------------------------------------
# 🔧  Low‑level helper coroutines (НЕ видны агенту)
# ---------------------------------------------------------------------------


async def _delete_user_messages(wrapper: RunContextWrapper[TaskContext]) -> bool:

    ctx = wrapper.context
    print(f'delete_user_messages .... ctx.message.message_id={ctx.message.message_id}')
    try:
        await ctx.message.delete()
        logger.info("Сообщение %s удалено", ctx.message.message_id)
        return True
    except Exception as exc:
        logger.exception("Ошибка при удалении сообщения: %s", exc)
        return False



async def _forward_message(wrapper: RunContextWrapper[TaskContext]):
    ctx = wrapper.context
    print(f'forward_message ....ctx.message.message_id={ctx.message.message_id}')
    try:
        await ctx.message.bot.forward_message(
            chat_id=ctx.target_group_id,
            from_chat_id=ctx.message.chat.id,
            message_id=ctx.message.message_id,
        )
        logger.info("Сообщение %s переслано модераторам", ctx.message.message_id)
        return {"status": "success"}
    except Exception as exc:
        logger.exception("Ошибка при пересылке сообщения: %s", exc)
        return {"status": "error", "details": str(exc)}


# ---------------------------------------------------------------------------
# 🏗️  High‑level tool, доступный агенту
# ---------------------------------------------------------------------------


@function_tool
async def process_spam(wrapper: RunContextWrapper[TaskContext]):
    """Полный цикл обработки спама (forward ➜ delete)."""
    print(f'process_spam ....')

    await _forward_message(wrapper)
    await _delete_user_messages(wrapper)

    return {"status": "done"}


# ---------------------------------------------------------------------------
# 📜  Агент и его инструкции
# ---------------------------------------------------------------------------

instructions = """
Ты — высокоточная система детекции спама для Telegram. Анализируй входные сообщения на предмет спама.

### Критерии СПАМА (отвечать «SPAM»):
… (оставьте существующие пункты без изменений) …

### Дополнительные указания
1. Любое сочетание «конкретная сумма + призыв к действию» → СПАМ.
2. Технические термины перевешивают спам‑маркеры.
3. Короткие сообщения («GPUStack») не считаются спамом.

---
**Формат ответа:**
- Если обнаружен спам, ответ должен быть строго:

  SPAM: {{process_spam()}}

- Если спама нет, то:

  NOT_SPAM
"""

agent = Agent(
    name="AntiSpamAgent",
    instructions=instructions,
    tools=[process_spam],  # ⬅️  Агент видит только один инструмент
    model=model,
)

# ---------------------------------------------------------------------------
# 🚀  Entry‑point for application code
# ---------------------------------------------------------------------------


async def agent_check_spam(message: types.Message):
    """Вызывается из aiogram‑хэндлера для проверки сообщения на спам."""

    task_context = TaskContext(
        sender_full_name=message.from_user.full_name,
        target_group_id=TARGET_GROUP_ID,
        message_text=message.text or "",
        message=message,
    )

    convo: list[TResponseInputItem] = [
        {"role": "user", "content": message.text or ""}
    ]

    result = await Runner.run(agent, convo, context=task_context)
    logger.info("Agent output: %s", result.final_output)

    return result
