# https://langchain-ai.github.io/langgraph/tutorials/get-started/1-build-basic-chatbot/
from dotenv import load_dotenv
from typing import Annotated
from langchain_openai import ChatOpenAI

from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    # Сообщения имеют тип "список". Функция `add_messages`
    # в аннотации определяет, как этот ключ состояния должен обновляться
    # (в этом случае она добавляет сообщения в список, а не перезаписывает их)
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

import os
from langchain.chat_models import init_chat_model

os.environ["OPENAI_API_KEY"] = "No Need"
load_dotenv()
OPENAI_BASE_URL = "http://localhost:11434/v1"
LOCAL_LLM       = os.getenv("LOCAL_LLM")

llm = ChatOpenAI(
    model_name=LOCAL_LLM,
    base_url   =OPENAI_BASE_URL,
    streaming  =False,
    temperature=0.0,
)

def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
# Первый аргумент — уникальное имя узла
# Второй аргумент — функция или объект, который будет вызываться всякий раз,
# когда используется узел.
graph_builder.add_node("chatbot", chatbot)

graph_builder.add_edge(START, "chatbot")

graph = graph_builder.compile()

try:

    # Сохраняем картинку в файл
    graph_image = graph.get_graph().draw_mermaid_png()
    with open("../graph_image.png", "wb") as png:
        png.write(graph_image)

except Exception:
    # This requires some extra dependencies and is optional
    # Это требует некоторых дополнительных зависимостей и не является обязательным
    pass

def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)


while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "Что ты знаешь о LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break