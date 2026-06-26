"""
Admin Dashboard — Home page.

Run with: streamlit run app.py
Additional pages live under pages/ and appear automatically in the
Streamlit sidebar navigation.
"""
import streamlit as st

from api_client import api_get

st.set_page_config(
    page_title="WhatsApp RAG Assistant — Admin",
    page_icon="💬",
    layout="wide",
)

st.title("💬 AI WhatsApp Customer Support Assistant")
st.caption("Admin dashboard — overview, conversations, knowledge base, and analytics")

st.divider()

data = api_get("/analytics", params={"days": 30})

if data:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Conversations (30d)", data["total_conversations"])
    col2.metric("Messages received (30d)", data["total_messages_in"])
    col3.metric("LLM requests (30d)", data["total_llm_requests"])
    col4.metric("Errors (30d)", data["total_errors"], delta_color="inverse")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Total customers", data["total_users"])
    col6.metric("Escalation rate", f"{data['escalation_rate'] * 100:.1f}%")
    avg_conf = data["avg_confidence_score"]
    col7.metric("Avg. AI confidence", f"{avg_conf:.2f}" if avg_conf is not None else "—")
    avg_rating = data["feedback_avg_rating"]
    col8.metric(
        "Avg. customer rating",
        f"{avg_rating:.1f} / 5" if avg_rating is not None else "—",
        help=f"Based on {data['feedback_count']} ratings",
    )

    st.divider()
    st.subheader("Quick links")
    st.markdown(
        "- **Conversations** — browse full customer chat threads and escalations\n"
        "- **Documents** — upload knowledge base files and trigger reindexing\n"
        "- **Analytics** — message/LLM/error trends over time\n"
        "- **Feedback** — customer satisfaction ratings on AI responses"
    )
else:
    st.warning(
        "Couldn't load data from the backend. Make sure the FastAPI service is "
        "running and `BACKEND_URL` / `ADMIN_API_KEY` are configured correctly "
        "for the dashboard."
    )
