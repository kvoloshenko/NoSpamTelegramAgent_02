from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, function_tool, RunContextWrapper, \
    TResponseInputItem
import os
from dotenv import load_dotenv
from spam_storage import save_spam_message
from dataclasses import dataclass
from aiogram import types

os.environ["OPENAI_API_KEY"] = "No Need"

load_dotenv()

LOCAL_LLM = os.getenv('LOCAL_LLM')
print(f'LOCAL_LLM = {LOCAL_LLM}')
TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID')
print(f'TARGET_GROUP_ID ={TARGET_GROUP_ID}')

model = OpenAIChatCompletionsModel(
    model=LOCAL_LLM,
    openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1")
)


@dataclass
class TaskContext:
    sender_full_name: str
    target_group_id: str
    message_text: str
    message: types.Message

@function_tool
async def delete_user_messages(wrapper: RunContextWrapper[TaskContext]) -> bool:
    """
    Удаляет текущее сообщение пользователя с использованием контекста сообщения
    """
    context = wrapper.context
    try:
        message = context.message
        await message.delete()
        print(f"Сообщение {message.message_id} удалено.")
        return True
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
        return False

@function_tool
async def save_spam(wrapper: RunContextWrapper[TaskContext]):
    """Сохраняет спам в базу с использованием контекста сообщения"""
    try:
        # Извлекаем контекст из обертки
        context = wrapper.context
        sender_full_name = context.sender_full_name
        message_text = context.message_text
        # Вызываем функцию сохранения спама с актуальными данными
        save_spam_message(sender_full_name, message_text)
        print(f"Spam saved. \nsender_full_name={sender_full_name}, \nmessage_text={message_text}")
        return {"status": "success"}
    except Exception as e:
        print(f"Save error: {e}")
        return {"status": "error", "details": str(e)}


@function_tool
async def forward_message(wrapper: RunContextWrapper[TaskContext]):
    """Пересылает сообщение модераторам с использованием контекста сообщения"""
    try:
        # Извлекаем контекст из обертки
        context = wrapper.context
        message = context.message
        chat_id = context.target_group_id
        from_chat_id = message.chat.id
        message_id = message.message_id
        print(f"Forwarded message chat_id={chat_id}, from_chat_id={from_chat_id}, message_id={message_id}")
        await message.bot.forward_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id
        )

        return {"status": "success"}
    except Exception as e:
        print(f"Forward error: {e}")
        return {"status": "error", "details": str(e)}


instructions = """Ты — высокоточная система детекции спама для Telegram. Анализируй сообщения строго по нижеуказанным правилам.

### Критерии СПАМА (отвечать "SPAM"):
... [все предыдущие критерии остаются без изменений] ...

### Особые указания:
1. Любое сочетание "конкретная сумма + призыв к действию" = SPAM
2. Технические термины перевешивают спам-маркеры
3. Короткие сообщения ("GPUStack") не считаются спамом

    1. Дай ответ в формате: SPAM ИЛИ NOT_SPAM

    При обнаружении спама (ответ SPAM) действуй в строгой последовательности и выполни эти три действия:
    1. Вызови {{save_spam()}}.
    2. Затем вызови {{forward_message()}}.
    3. Затем вызови {{delete_user_messages()}}.

Ответ всегда в формате: 
SPAM: {{save_spam()}} → {{forward_message()}}
или 
NOT_SPAM.

Примеры:
- Сообщение: "Купите дешёвые акции!"
Ответ: SPAM: {{save_spam()}} → {{forward_message()}}
"""

agent = Agent(
    name="AntiSpamAgent",
    instructions=instructions,
    tools=[save_spam, forward_message, delete_user_messages],
    model=model
)


async def agent_check_spam(message: types.Message):
    # Создаем контекст с данными сообщения

    taskContext = TaskContext(sender_full_name=message.from_user.full_name,
                              target_group_id=TARGET_GROUP_ID,
                              message_text=message.text,
                              message=message)

    user_input = message.text
    convo_items: list[TResponseInputItem] = []
    convo_items.append({"content": user_input, "role": "user"})

    # Передаем данные в агент
    # result = Runner.run_sync(agent, convo_items, context=taskContext)
    result = await Runner.run(agent, convo_items, context=taskContext)
    print(f"result: {result.final_output}")
    print(type(result))
    # print("Called tools:", [tool_call.function_name for tool_call in result.tool_calls])

