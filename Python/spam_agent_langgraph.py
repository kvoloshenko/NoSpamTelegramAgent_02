"""
Anti-Spam agent implemented with LangGraph.
Guarantees the sequence:
save_spam() ➜ forward_message() ➜ delete_user_messages()
"""

import os
from dataclasses import dataclass
from typing import TypedDict, Optional, Any

from dotenv import load_dotenv
from aiogram import types

from langgraph.graph import StateGraph, END
from langchain.tools import tool
from langchain_ollama import ChatOllama
from spam_storage import save_spam_message   # ваша БД-функция
from langchain_core.messages import SystemMessage, HumanMessage

# ------------------------------------------------------------------ #
# ⬇️  Конфигурация окружения
# ------------------------------------------------------------------ #
load_dotenv()
OPENAI_BASE_URL = "http://localhost:11434/v1"
LOCAL_LLM       = os.getenv("LOCAL_LLM")
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))

llm = ChatOllama(model=LOCAL_LLM , temperature=0)
llm_json_mode = ChatOllama(model=LOCAL_LLM , temperature=0, format="json")

# llm = ChatOpenAI(
#     model_name=LOCAL_LLM,
#     base_url   =OPENAI_BASE_URL,
#     streaming  =False,
#     temperature=0.0,
# )

# ------------------------------------------------------------------ #
# ⬇️  Описание состояния графа
# ------------------------------------------------------------------ #
class AgentState(TypedDict, total=False):
    """Объект, который «путешествует» по графу"""
    message            : types.Message
    sender_full_name   : str
    target_group_id    : int
    is_spam            : bool
    classification_text: str          # ответ LLM (для логов)

# ------------------------------------------------------------------ #
# ⬇️  Узлы-действия
# ------------------------------------------------------------------ #
# Узел графа, который классифицирует сообщение
async def detect_spam(state: dict) -> dict:
    """
    state: {
        "message": str,   # текст сообщения пользователя
        ...
    }
    """
    user_text: str = state["message"]

    messages = [
        SystemMessage(
            content=(
                "Ты анти-спам-классификатор для Telegram-бота. "
                "Ответь ровно одной строкой: SPAM или OK."
            )
        ),
        HumanMessage(content=user_text),
    ]

    # ✅  Правильный асинхронный вызов
    response = await llm.ainvoke(messages)

    # Результат LLM
    state["result"] = response.content.strip().upper()
    return state



@tool("save_spam")
async def save_spam_tool(
    sender_full_name: str,
    message_text: str,
) -> dict:
    """Сохраняет спам-сообщение в базу"""
    save_spam_message(sender_full_name, message_text)
    return {"status": "saved"}


async def save_spam_node(state: AgentState) -> AgentState:
    """Node-обёртка над tool"""
    await save_spam_tool.ainvoke(
        {"sender_full_name": state["sender_full_name"],
         "message_text": state["message"].text or ""}
    )
    return state


async def forward_message_node(state: AgentState) -> AgentState:
    msg: types.Message = state["message"]
    await msg.bot.forward_message(
        chat_id=state["target_group_id"],
        from_chat_id=msg.chat.id,
        message_id=msg.message_id,
    )
    return state


async def delete_message_node(state: AgentState) -> AgentState:
    try:
        await state["message"].delete()
    except Exception:  # сообщение могло быть уже удалено
        pass
    return state

# ------------------------------------------------------------------ #
# ⬇️  Построение графа
# ------------------------------------------------------------------ #
graph = StateGraph(AgentState)

graph.add_node("detect_spam",        detect_spam)
graph.add_node("save_spam",          save_spam_node)
graph.add_node("forward_message",    forward_message_node)
graph.add_node("delete_user_message", delete_message_node)

# ── Условный переход после классификации ─────────────────────────── #
graph.add_conditional_edges(
    "detect_spam",
    lambda s: "save_spam" if s.get("is_spam") else END,
)

# ── Чёткая последовательность действий для спама ─────────────────── #
graph.add_edge("save_spam",           "forward_message")
graph.add_edge("forward_message",     "delete_user_message")
graph.add_edge("delete_user_message", END)

# ── Установка начальной точки графа ─────────────────────────────── #
graph.set_entry_point("detect_spam")

# ------------------------------------------------------------------ #
# ⬇️  Компиляция графа
# ------------------------------------------------------------------ #
graph_executor = graph.compile()

# ------------------------------------------------------------------ #
# ⬇️  Вызов из обработчика Telegram
# ------------------------------------------------------------------ #
async def agent_check_spam(message: types.Message) -> None:
    """Telegram-entry-point."""
    initial_state: AgentState = {
        "message"         : message,
        "sender_full_name": message.from_user.full_name,
        "target_group_id" : TARGET_GROUP_ID,
    }
    await graph_executor.ainvoke(initial_state)
