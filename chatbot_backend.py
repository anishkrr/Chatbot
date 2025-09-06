from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    USE_SQLITE = True
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver
    USE_SQLITE = False

import sqlite3

load_dotenv()


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    streaming=True
)

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

if USE_SQLITE:
    conn = sqlite3.connect(database="chatbot.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn=conn)
else:
    checkpointer = MemorySaver()

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    if USE_SQLITE:
        all_threads = set()
        for checkpoint in checkpointer.list(None):
            all_threads.add(checkpoint.config["configurable"]["thread_id"])
        return list(all_threads)
    else:
        return []  # no persistence in memory mode
