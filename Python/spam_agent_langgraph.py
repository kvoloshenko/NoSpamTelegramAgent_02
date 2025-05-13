"""
Anti-Spam agent implemented with LangGraph.
Guarantees the sequence:
save_spam() ➜ forward_message() ➜ delete_user_messages()
"""

import os
import logging
from typing import TypedDict

from dotenv import load_dotenv
from aiogram import types

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema.messages import HumanMessage
from langchain.tools import tool

from spam_storage import save_spam_message  # ваша БД-функция

# Настройка логгера
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# ⬇️ Конфигурация окружения
# ------------------------------------------------------------------ #
os.environ["OPENAI_API_KEY"] = "No Need"
load_dotenv()
OPENAI_BASE_URL = "http://localhost:11434/v1"
LOCAL_LLM = os.getenv("LOCAL_LLM")
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))

llm = ChatOpenAI(
    model_name=LOCAL_LLM,
    base_url=OPENAI_BASE_URL,
    streaming=False,
    temperature=0.0,
)


# ------------------------------------------------------------------ #
# ⬇️ Описание состояния графа
# ------------------------------------------------------------------ #
class AgentState(TypedDict, total=False):
    """Объект, который «путешествует» по графу"""
    message: types.Message
    sender_full_name: str
    target_group_id: int
    is_spam: bool
    classification_text: str  # ответ LLM (для логов)


# ------------------------------------------------------------------ #
# ⬇️ Узлы-действия с логированием
# ------------------------------------------------------------------ #
async def detect_spam(state: AgentState) -> AgentState:
    """LLM-классификация: SPAM / NOT_SPAM → is_spam bool"""
    logger.info("⏳ Выполнение узла detect_spam...")

    msg_text = state["message"].text or ""
    system_prompt = (
        "Ты — высокоточная система детекции спама для Telegram.\n"
        "Отвечай только 'SPAM' или 'NOT_SPAM' без пояснений.\n"
        """### Критерии SPAM (маркировать если есть ХОТЯ БЫ ОДИН признак):
1. **Финансовые предложения + контакт:**
   - Упоминание сумм ($, ₽, "доход", "прибыль") + призыв к действию ("пиши", "ЛС", "напиши", "жду в личку")
   - *Примеры:*
     ▸ "Доход 110$/день. Пишите в ЛС"
     ▸ "Получай 70$ в день — напиши мне плюс"

2. **Гарантии быстрой выгоды:**
   - Фразы: "без вложений", "без опыта", "всё просто", "без стрессов", "только N человек", "требуются люди"
   - *Примеры:*
     ▸ "Только 5 человек — забирайте 80% прибыли"
     ▸ "Без сложностей — 600$ в неделю"

3. **Шаблонные структуры:**
   - Приветствие + предложение + контакт:
     ▸ "Доброго дня! Открыто направление с доходом 250$/день. Пишите да"
     ▸ "Здравствуйте! Нужны люди для заработка 70$ — обсудим в ЛС"
   - Упоминание "форматов" или "партнёрств":
     ▸ "Партнёрство 80/20: ваши 80% без рутины"
     ▸ "Рабочий формат: телефон + $15/час"

4. **Скрытые маркеры:**
   - Удалёнка + доход + устройство:
     ▸ "Удалёнка без начальников. Телефон + $13/час"
     ▸ "Смартфон = $15/час. Пиши за деталями"
   - Манипуляции: "Срочно!", "Немедленно смените пароль", "Уникальная возможность"

### Критерии NOT_SPAM (только при ОТСУТСТВИИ всех признаков выше):
- **Технические обсуждения:**
  ▸ Квантование моделей ("Q4_K_M", "Q8"), fine-tuning, ИИ-архитектуры
  ▸ Вопросы про нейросети ("whisper на казахском", "vllm", "векторные базы")
- **Рабочие вопросы:**
  ▸ Встречи ("сегодня в 18:00"), документы, трек-номера
- **Аналитика:**
  ▸ Обсуждение ChatGPT, локальных моделей, проблем ИИ
- **Личные диалоги:**
  ▸ "Что думаете о...", "Был похожий случай...", гипотезы об эпохе ИИ

### Автоматические правила:
1. **Любое сочетание** "деньги ($/₽)" + "контакт (ЛС/пиши)" → SPAM
2. **Любое упоминание** "розыгрыша", "взлома", "партнёрства" с цифрами → SPAM
3. **Игнорировать:**
   - Опечатки, длину текста, вежливые приветствия
   - Обсуждение математики, университетов, если нет финансовых предложений

### Примеры для привязки:
- **SPAM:**
  "Приветствую! Доход 600$/неделя. Напиши в ЛС → Без опыта!"
  "Делюсь форматом: смартфон + $14/час. Жду в личку!"
  "Заработай 250$/день. Пиши 'Да' → Только сегодня!"
- **NOT_SPAM:**
  "Как квантовать модель для Q8?"
  "Почему ChatGPT стал угодливым?"
  "Трек-номер AB123456 готов"
=================================================="""
        f"Сообщение: «{msg_text}»"
    )

    logger.debug(f"Отправка запроса к LLM: {system_prompt[:100]}...")
    answer = await llm.ainvoke([HumanMessage(content=system_prompt)])
    answer_content = answer.content

    state["classification_text"] = answer_content
    state["is_spam"] = answer_content.strip().upper().startswith("SPAM")

    logger.info(f"🔍 Результат классификации: {'SPAM' if state['is_spam'] else 'NOT_SPAM'}")
    logger.info("✅ Узел detect_spam завершен")
    return state


@tool("save_spam")
async def save_spam_tool(
        sender_full_name: str,
        message_text: str,
) -> dict:
    """Сохраняет спам-сообщение в базу"""
    logger.info("💾 Сохранение спама в БД...")
    save_spam_message(sender_full_name, message_text)
    return {"status": "saved"}


async def save_spam_node(state: AgentState) -> AgentState:
    """Node-обёртка над tool"""
    logger.info("⏳ Выполнение узла save_spam...")
    await save_spam_tool.ainvoke({
        "sender_full_name": state["sender_full_name"],
        "message_text": state["message"].text or ""
    })
    logger.info("✅ Узел save_spam завершен")
    return state


async def forward_message_node(state: AgentState) -> AgentState:
    logger.info("⏳ Выполнение узла forward_message...")
    msg: types.Message = state["message"]

    logger.debug(f"Пересылка сообщения в группу {state['target_group_id']}")
    await msg.bot.forward_message(
        chat_id=state["target_group_id"],
        from_chat_id=msg.chat.id,
        message_id=msg.message_id,
    )

    logger.info("✅ Сообщение переслано")
    logger.info("✅ Узел forward_message завершен")
    return state


async def delete_message_node(state: AgentState) -> AgentState:
    logger.info("⏳ Выполнение узла delete_user_message...")
    try:
        await state["message"].delete()
        logger.info("✅ Сообщение удалено")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить сообщение: {str(e)}")
    logger.info("✅ Узел delete_user_message завершен")
    return state


# ------------------------------------------------------------------ #
# ⬇️ Построение графа
# ------------------------------------------------------------------ #
graph = StateGraph(AgentState)

graph.add_node("detect_spam", detect_spam)
graph.add_node("save_spam", save_spam_node)
graph.add_node("forward_message", forward_message_node)
graph.add_node("delete_user_message", delete_message_node)

# Установка точки входа
graph.set_entry_point("detect_spam")


# Условный переход после классификации
def route_decision(state: AgentState) -> str:
    if state.get("is_spam"):
        logger.info("🔄 Переход к обработке спама")
        return "save_spam"
    logger.info("🛑 Сообщение не спам, завершение обработки")
    return END


graph.add_conditional_edges(
    "detect_spam",
    route_decision,
)

# Чёткая последовательность действий для спама
graph.add_edge("save_spam", "forward_message")
graph.add_edge("forward_message", "delete_user_message")
graph.add_edge("delete_user_message", END)

# ------------------------------------------------------------------ #
# ⬇️ Компиляция графа
# ------------------------------------------------------------------ #
graph_executor = graph.compile()

try:
    logger.info("Сохраняем картинку в файл")
    # Сохраняем картинку в файл
    graph_image = graph_executor.get_graph().draw_mermaid_png()
    with open("../graph_image.png", "wb") as png:
        png.write(graph_image)

except Exception:
    # This requires some extra dependencies and is optional
    # Это требует некоторых дополнительных зависимостей и не является обязательным
    logger.info(" Не удалось сохранить картинку в файл")

# ------------------------------------------------------------------ #
# ⬇️ Вызов из обработчика Telegram
# ------------------------------------------------------------------ #
async def agent_check_spam(message: types.Message) -> None:
    """Telegram-entry-point."""
    logger.info(f"\n🔔 Новое сообщение от @{message.from_user.username}: {message.text[:50]}...")
    initial_state: AgentState = {
        "message": message,
        "sender_full_name": message.from_user.full_name,
        "target_group_id": TARGET_GROUP_ID,
    }
    await graph_executor.ainvoke(initial_state)
    logger.info("🏁 Обработка сообщения завершена\n")