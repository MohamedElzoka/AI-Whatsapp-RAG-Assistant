"""
Analytics page: timeseries charts for incoming messages, LLM requests,
and errors, plus headline KPIs for a selectable lookback window.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import api_get

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")
st.title("📊 Analytics")

days = st.slider("Lookback window (days)", min_value=1, max_value=90, value=30)

data = api_get("/analytics", params={"days": days})

if not data:
    st.stop()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Messages in", data["total_messages_in"])
col2.metric("Messages out", data["total_messages_out"])
col3.metric("LLM requests", data["total_llm_requests"])
col4.metric("Errors", data["total_errors"])
col5.metric("Escalations", data["escalation_count"])

st.divider()


def _ts_df(points: list[dict], label: str) -> pd.DataFrame:
    if not points:
        return pd.DataFrame({"date": [], label: []})
    df = pd.DataFrame(points).rename(columns={"count": label})
    df["date"] = pd.to_datetime(df["date"])
    return df


tab1, tab2, tab3 = st.tabs(["Incoming messages", "LLM requests", "Errors"])

with tab1:
    df = _ts_df(data["messages_per_day"], "Messages")
    if not df.empty:
        fig = px.line(df, x="date", y="Messages", markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No message data in this window yet.")

with tab2:
    df = _ts_df(data["llm_requests_per_day"], "LLM requests")
    if not df.empty:
        fig = px.line(df, x="date", y="LLM requests", markers=True, color_discrete_sequence=["#6c63ff"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No LLM request data in this window yet.")

with tab3:
    df = _ts_df(data["errors_per_day"], "Errors")
    if not df.empty:
        fig = px.bar(df, x="date", y="Errors", color_discrete_sequence=["#e74c3c"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("No errors recorded in this window. 🎉")
