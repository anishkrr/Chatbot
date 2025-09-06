import streamlit as st
from chatbot_backend import chatbot, retrieve_all_threads
from langchain_core.messages import HumanMessage
import uuid
from datetime import datetime
import io

# **************************************** utility functions *************************

def generate_thread_id():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(thread_id, summary=None)
    st.session_state['message_history'] = []

def add_thread(thread_id, summary=None):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'][thread_id] = {
            "summary": summary if summary else "New Chat",
            "messages": []
        }

def load_conversation(thread_id):
    messages = chatbot.get_state(config={'configurable': {'thread_id': thread_id}}).values['messages']
    temp_messages = []
    for msg in messages:
        role = 'user' if isinstance(msg, HumanMessage) else 'assistant'
        temp_messages.append({
            'role': role,
            'content': msg.content,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # fallback
        })
    return temp_messages

def update_summary(thread_id, first_message):
    """Use first user message as thread summary"""
    if st.session_state['chat_threads'][thread_id]["summary"] == "New Chat":
        st.session_state['chat_threads'][thread_id]["summary"] = first_message[:40] + "..."

def download_conversation(thread_id):
    """Generate downloadable text file of conversation"""
    messages = st.session_state['chat_threads'][thread_id]["messages"]
    chat_text = ""
    for msg in messages:
        chat_text += f"[{msg.get('timestamp','')}] {msg['role'].capitalize()}: {msg['content']}\n"
    return chat_text


# **************************************** Session Setup ******************************
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = {}

# load all past threads from backend (SQLite)
all_threads = retrieve_all_threads()
for thread_id in all_threads:
    if thread_id not in st.session_state['chat_threads']:
        # load messages from backend
        temp_messages = load_conversation(thread_id)
        # first user message as summary
        summary = next((m['content'] for m in temp_messages if m['role'] == 'user'), "New Chat")
        st.session_state['chat_threads'][thread_id] = {
            "summary": summary[:40] + "...",
            "messages": temp_messages
        }

# if no active thread, pick the first
if 'thread_id' not in st.session_state:
    if all_threads:
        st.session_state['thread_id'] = all_threads[0]
    else:
        st.session_state['thread_id'] = str(uuid.uuid4())
        st.session_state['chat_threads'][st.session_state['thread_id']] = {"summary": "New Chat", "messages": []}

# load the current message history
st.session_state['message_history'] = st.session_state['chat_threads'][st.session_state['thread_id']]["messages"]


# **************************************** Sidebar UI *********************************

st.sidebar.title('LangGraph Chatbot')

if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')

# --- Search bar ---
search_query = st.sidebar.text_input("🔍 Search conversations")

for thread_id, thread_data in list(st.session_state['chat_threads'].items())[::-1]:
    summary = thread_data["summary"]

    if search_query.lower() in summary.lower():
        if st.sidebar.button(summary, key=thread_id):
            st.session_state['thread_id'] = thread_id
            st.session_state['message_history'] = thread_data["messages"]


# **************************************** Main UI ************************************

# loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(f"{message['content']}  \n🕒 {message.get('timestamp','')}")

user_input = st.chat_input('Type here')

if user_input:
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    # Show user message immediately
    with st.chat_message('user'):
        st.text(f"{user_input}  \n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # assistant streaming response
    with st.chat_message('assistant'):
        st.write_stream(
            message_chunk.content for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages'
            )
        )

    # ✅ Reload conversation from backend to avoid duplicates
    updated_messages = load_conversation(st.session_state['thread_id'])
    st.session_state['message_history'] = updated_messages
    st.session_state['chat_threads'][st.session_state['thread_id']]["messages"] = updated_messages

    # set summary if first user message
    update_summary(st.session_state['thread_id'], user_input)


# **************************************** Download Conversation ************************

if st.session_state['thread_id'] in st.session_state['chat_threads']:
    chat_text = download_conversation(st.session_state['thread_id'])
    st.sidebar.download_button(
        label="📥 Download Conversation",
        data=chat_text,
        file_name=f"chat_{st.session_state['thread_id']}.txt",
        mime="text/plain"
    )
