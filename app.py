import os
import uuid

import streamlit as st

from core.chat_store import ensure_conversation, recent_context, save_message
from core.models import get_model_name
from graph import graph


st.set_page_config(
    page_title="Cora",
    page_icon="🧠",
    layout="centered",
)

active_model = get_model_name("supervisor")

st.title("Cora")
st.caption(f"Assistente multi-agente locale — {active_model}")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    ensure_conversation(
        st.session_state.thread_id,
        metadata={"interface": "streamlit"},
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Scrivi un messaggio a Cora..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Cora sta pensando..."):
            user_message = save_message(
                conversation_id=st.session_state.thread_id,
                role="user",
                content=prompt,
                agent_id="user",
                metadata={"source": "streamlit"},
            )
            result = graph.invoke(
                {"messages": recent_context(st.session_state.thread_id)}
            )
            response = result["messages"][-1].content
            save_message(
                conversation_id=st.session_state.thread_id,
                role="assistant",
                content=response,
                agent_id="supervisor",
                model_id=active_model,
                parent_message_id=str(user_message["id"]),
                metadata={"source": "streamlit"},
            )
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
