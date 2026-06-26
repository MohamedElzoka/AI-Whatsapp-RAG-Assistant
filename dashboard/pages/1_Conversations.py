"""
Conversations page: browse and drill into customer chat threads.
"""
import pandas as pd
import streamlit as st

from api_client import api_get

st.set_page_config(page_title="Conversations", page_icon="🗂️", layout="wide")
st.title("🗂️ Conversations")

with st.sidebar:
    st.header("Filters")
    phone_filter = st.text_input("Customer phone contains")
    status_filter = st.selectbox("Status", ["", "open", "escalated", "closed"])
    escalated_only = st.checkbox("Escalated only")
    page = st.number_input("Page", min_value=1, value=1, step=1)

params = {"page": page, "page_size": 20}
if phone_filter:
    params["phone"] = phone_filter
if status_filter:
    params["status"] = status_filter
if escalated_only:
    params["escalated_only"] = True

data = api_get("/conversations", params=params)

if not data:
    st.stop()

st.caption(f"{data['total']} total conversations — page {data['page']}")

if not data["conversations"]:
    st.info("No conversations match the current filters.")
    st.stop()

df = pd.DataFrame(data["conversations"])
df_display = df[["id", "user_phone", "started_at", "status", "escalated", "message_count", "last_message_preview"]]
st.dataframe(df_display, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Inspect a conversation")
selected_id = st.selectbox("Conversation ID", options=df["id"].tolist())

if selected_id:
    detail = api_get(f"/conversations/{selected_id}")
    if detail:
        st.markdown(
            f"**Customer:** {detail['user_phone']}  \n"
            f"**Status:** {detail['status']}  "
            f"{'🔴 Escalated (' + detail['escalation_reason'] + ')' if detail['escalated'] else ''}  \n"
            f"**Started:** {detail['started_at']}"
        )
        st.divider()
        for msg in detail["messages"]:
            role = "🧑 Customer" if msg["sender"] == "customer" else (
                "🤖 Assistant" if msg["sender"] == "assistant" else "👤 Human agent"
            )
            with st.chat_message("user" if msg["sender"] == "customer" else "assistant"):
                st.markdown(f"**{role}** · {msg['timestamp']}")
                st.write(msg["content"])
                if msg["confidence_score"] is not None:
                    st.caption(f"Confidence: {msg['confidence_score']:.2f}")
