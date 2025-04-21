from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, function_tool, RunContextWrapper, TResponseInputItem
import os
from dotenv import load_dotenv
from spam_storage import save_spam_message
from dataclasses import dataclass

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

@dataclass
class UserProfile:
    sender_full_name: str
    message_text: str


@function_tool
async def save_spam(wrapper: RunContextWrapper[UserProfile]):
    """Сохраняет спам в базу с использованием контекста сообщения"""
    try:
        # TODO call save_spam_message
        # save_spam_message(context.sender_full_name, context.message_text)
        # print(f"Spam saved. \nsender_full_name={context.sender_full_nam}, \nmessage_text={context.message_text}")
        return {"status": "success"}
    except Exception as e:
        print(f"Save error: {e}")
        return {"status": "error", "details": str(e)}

instructions = """Ты — высокоточная система детекции спама для Telegram. Анализируй сообщения строго по нижеуказанным правилам.

### Критерии СПАМА (отвечать "SPAM"):
... [все предыдущие критерии остаются без изменений] ...

### Особые указания:
1. Любое сочетание "конкретная сумма + призыв к действию" = SPAM
2. Технические термины перевешивают спам-маркеры
3. Короткие сообщения ("GPUStack") не считаются спамом

    1. Дай ответ в формате: SPAM ИЛИ NOT_SPAM
    2. Для SPAM выполни:
    2.1 Сохрани запись через save_spam, используя контекст сообщения
"""

agent = Agent[MessageContext](
    name="AntiSpamAgent",
    instructions=instructions,
    tools=[save_spam],
    model=model
)

convo_items: list[TResponseInputItem] = []

# Создаем контекст с данными сообщения
profile = UserProfile(sender_full_name="Konstantin Voloshenko",
                      message_text="Здравствуйте! Есть возможность получать от 195 долларов в день. Заинтересованы? Пишите в личные сообщения")

user_input = "Здравствуйте! Есть возможность получать от 195 долларов в день. Заинтересованы? Пишите в личные сообщения"
convo_items.append({"content": user_input, "role": "user"})

# Передаем данные в агент
result = Runner.run_sync(agent, convo_items, context=profile)
print(f"result: {result.final_output}")
print(type(result))