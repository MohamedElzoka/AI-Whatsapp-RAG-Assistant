"""
Documents page: upload knowledge base files (PDF/DOCX/TXT) and trigger
a full reindex of the vector store.
"""
import pandas as pd
import streamlit as st

from api_client import api_get, api_post

st.set_page_config(page_title="Documents", page_icon="📄", layout="wide")
st.title("📄 Knowledge Base Documents")

st.subheader("Upload a document")
st.caption("Supported formats: PDF, DOCX, TXT. Files are chunked, embedded, and indexed automatically.")

uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "txt"])

if uploaded_file is not None:
    if st.button("Upload & Index", type="primary"):
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        }
        with st.spinner("Uploading and queuing for indexing..."):
            result = api_post("/documents/upload", files=files)
        if result:
            st.success(result.get("message", "Uploaded."))
            st.rerun()

st.divider()

col_left, col_right = st.columns([3, 1])
with col_left:
    st.subheader("Indexed documents")
with col_right:
    if st.button("🔄 Reindex entire knowledge base"):
        with st.spinner("Rebuilding vector index from all documents..."):
            result = api_post("/documents/reindex")
        if result:
            st.success(
                f"Reindex started for {result['documents_queued']} document(s). "
                "Refresh in a moment to see updated status."
            )

documents = api_get("/documents")

if documents:
    df = pd.DataFrame(documents)
    df_display = df[["filename", "file_type", "status", "chunk_count", "uploaded_at", "indexed_at", "error_message"]]

    def highlight_status(row):
        color = {
            "indexed": "background-color: #d4edda",
            "failed": "background-color: #f8d7da",
            "indexing": "background-color: #fff3cd",
            "pending": "background-color: #e2e3e5",
        }.get(row["status"], "")
        return [color] * len(row)

    st.dataframe(
        df_display.style.apply(highlight_status, axis=1),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No documents uploaded yet.")
