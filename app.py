import uuid
import streamlit as st
from graph import graph

st.set_page_config(
    page_title="Cora",
    page_icon="🧠",
    layout="centered",
)

st.title("Cora")
st.caption("Assistente multi-agente locale — gpt-oss:20b")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Scrivi un messaggio a Cora..."):
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Cora sta pensando..."):
            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            result = graph.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ]
                },
                config=config,
            )

            response = result["messages"][-1].content
            st.markdown(response)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
    })
