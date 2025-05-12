"""
spam_agent_langgraph.py

Асинхронный LangGraph-агент антиспама для Telegram-бота.
Главное исправление: в граф передаётся только строка с текстом
(`user_text`), а не объект `aiogram.types.Message`, чтобы не падать
на валидации `langchain_core.messages.HumanMessage`.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from aiogram import types
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
# from langchain_openai import ChatOpenAI          # pip install langchain-openai
from langgraph.graph import StateGraph, END       # pip install langgraph
from langchain_ollama import ChatOllama

# -----------------------------------------------------------------------------
# базовая настройка окружения и логирования
# -----------------------------------------------------------------------------
load_dotenv()
OPENAI_BASE_URL = "http://localhost:11434/v1"
LOCAL_LLM       = os.getenv("LOCAL_LLM")
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID"))

llm = ChatOllama(model=LOCAL_LLM , temperature=0)
llm_json_mode = ChatOllama(model=LOCAL_LLM , temperature=0, format="json")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")      # ключ к OpenAI падаёт из .env
# LLM_MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")


llm = ChatOllama(model=LOCAL_LLM , temperature=0)
llm_json_mode = ChatOllama(model=LOCAL_LLM , temperature=0, format="json")
# llm = ChatOpenAI(
#     model_name=LLM_MODEL_NAME,
#     temperature=0.0,
#     openai_api_key=OPENAI_API_KEY,
#     streaming=False,          # нам не нужен стриминг в этом кейсе
# )

# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
def _extract_text(msg: types.Message) -> str:
    """
    Возвращаем текст для обычных сообщений или caption для медиа;
    если ничего нет — пустую строку.
    """
    return msg.text or msg.caption or ""


# -----------------------------------------------------------------------------
# узлы LangGraph
# -----------------------------------------------------------------------------
async def detect_spam(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Проверяем текст через LLM, возвращаем флаг is_spam.
    В state гарантированно лежит строка `user_text`.
    """
    user_text: str = state["user_text"]

    logger.debug("Запускаем LLM-проверку спама…")

    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "Ты — антиспам-фильтр Telegram-бота.\n"
                    "Твоя задача: ответить ровно одним словом без кавычек:\n"
                    "«SPAM», если сообщение похоже на спам,\n"
                    "или «OK», если всё в порядке."
                )
            ),
            HumanMessage(content=user_text),
        ]
    )

    verdict = response.content.strip().upper()
    is_spam = verdict.startswith("SPAM")

    logger.info("LLM verdict for message «%s…»: %s", user_text[:40], verdict)
    return {"is_spam": is_spam}


async def route(state: Dict[str, Any]) -> str:
    """
    Кондишен-функция (router) для ветвления графа.
    """
    return "spam" if state["is_spam"] else "ok"


async def action_spam(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Если сообщение спам — пытаемся его удалить.
    """
    msg: types.Message = state["telegram_message"]
    try:
        await msg.delete()
        logger.info("Удалено спам-сообщение %s", msg.message_id)
    except Exception as e:                       # noqa: BLE001
        logger.exception("Не удалось удалить спам-сообщение: %s", e)
    return {}


async def action_ok(_: Dict[str, Any]) -> Dict[str, Any]:
    """
    Сообщение не спам — ничего не делаем.
    """
    return {}


# -----------------------------------------------------------------------------
# построение графа
# -----------------------------------------------------------------------------
graph = StateGraph()

graph.add_node("check_spam", detect_spam)
graph.add_node("spam_action", action_spam)
graph.add_node("ok_action", action_ok)

graph.set_entry_point("check_spam")
graph.add_conditional_edges(
    source="check_spam",
    condition=route,
    path_map={
        "spam": "spam_action",
        "ok": "ok_action",
    },
)

graph.add_edge("spam_action", END)
graph.add_edge("ok_action", END)

graph_executor = graph.compile()


# -----------------------------------------------------------------------------
# публичная функция, вызываемая из main.py
# -----------------------------------------------------------------------------
async def agent_check_spam(message: types.Message) -> None:
    """
    Функция-обёртка: подготавливает initial_state и стартует граф.
    """
    user_text = _extract_text(message)
    if not user_text:
        logger.info("Получено сообщение без текста – проверка спама пропущена")
        return

    initial_state: Dict[str, Any] = {
        "user_text": user_text,      # str, на основе чего работает LLM
        "telegram_message": message  # оригинальный объект, нужен для delete()
    }

    await graph_executor.ainvoke(initial_state)
