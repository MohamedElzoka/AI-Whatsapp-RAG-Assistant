"""
Feedback page: distribution of customer ratings on AI responses, plus a
browsable table of individual feedback entries with comments.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import api_get

st.set_page_config(page_title="Feedback", page_icon="⭐", layout="wide")
st.title("⭐ Customer Feedback")

feedback = api_get("/conversations/feedback/all")

if not feedback:
    st.info("No feedback has been submitted yet.")
    st.stop()

df = pd.DataFrame(feedback)

col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Total ratings", len(df))
    st.metric("Average rating", f"{df['rating'].mean():.2f} / 5")

with col2:
    counts = df["rating"].value_counts().sort_index()
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        labels={"x": "Rating", "y": "Count"},
        title="Rating distribution",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("All feedback")

min_rating = st.slider("Show ratings at or below", min_value=1, max_value=5, value=5)
filtered = df[df["rating"] <= min_rating]

st.dataframe(
    filtered[["user_phone", "rating", "comment", "message_content", "created_at"]],
    use_container_width=True,
    hide_index=True,
)
