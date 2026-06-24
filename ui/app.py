"""
DocuChat RAG - Streamlit UI (Project-based API)

Chat interface for the GRC RAG Governance Assistant.
Automatically creates/reuses a default GRC project on startup.
"""

import streamlit as st
import requests
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE_URL = "http://localhost:8000/api"
DEFAULT_PROJECT_NAME = "GRC Knowledge Assistant"
DEFAULT_SYSTEM_PROMPT = (
    "You are a GRC and cloud security expert. "
    "Answer only from the provided documents. "
    "Always cite your sources. "
    "If the answer is not in the documents, say you do not know."
)
REQUEST_TIMEOUT = 180  # 3 min — first query downloads HuggingFace model

st.set_page_config(
    page_title="GRC RAG Assistant",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stChatMessage { border-radius: 12px; }
    .citation-box {
        background: #1e293b;
        border-left: 3px solid #3b82f6;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.85em;
        margin: 4px 0;
    }
    .confidence-high { color: #22c55e; font-weight: bold; }
    .confidence-mid  { color: #f59e0b; font-weight: bold; }
    .confidence-low  { color: #ef4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(path: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}{path}", timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def get_or_create_project() -> Optional[str]:
    """Return the default GRC project ID, creating it if it doesn't exist."""
    projects = api_get("/projects")
    if projects:
        for p in projects:
            if p.get("name") == DEFAULT_PROJECT_NAME:
                return p["id"]

    # Create it
    try:
        r = requests.post(
            f"{API_BASE_URL}/projects",
            json={
                "name": DEFAULT_PROJECT_NAME,
                "description": "RAG assistant for AI governance, risk, compliance and cloud security.",
                "system_prompt": DEFAULT_SYSTEM_PROMPT,
                "top_k": 5,
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()["id"]
    except Exception:
        pass
    return None


def upload_document(project_id: str, file) -> Optional[dict]:
    try:
        files = {"file": (file.name, file.getvalue(), "application/octet-stream")}
        r = requests.post(
            f"{API_BASE_URL}/projects/{project_id}/upload",
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        st.error(f"Upload failed: {r.json().get('detail', r.text)}")
    except requests.exceptions.Timeout:
        st.error("Upload timed out — the document may be large. Try again.")
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def query(project_id: str, question: str) -> Optional[dict]:
    try:
        r = requests.post(
            f"{API_BASE_URL}/projects/{project_id}/query",
            json={"question": question, "include_diagnostics": False},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        st.error(f"Query failed: {r.json().get('detail', r.text)}")
    except requests.exceptions.Timeout:
        st.error(
            "⏳ Query timed out (3 min). "
            "On first query the embedding model downloads (~90MB). "
            "Check the backend terminal — once you see 'Uvicorn running' messages again, retry."
        )
    except Exception as e:
        st.error(f"Connection error: {e}")
    return None


def list_documents(project_id: str) -> list:
    result = api_get(f"/projects/{project_id}/documents")
    return result or []


# ── Main app ──────────────────────────────────────────────────────────────────

def main():
    # ── Header ────────────────────────────────────────────────────────────────
    st.title("🔐 GRC RAG Governance Assistant")
    st.caption("AI-powered Q&A over your GRC, risk, and cloud security documents")

    # ── Check API health ──────────────────────────────────────────────────────
    health = api_get("/health")
    api_ok = health is not None

    # ── Get or create project ─────────────────────────────────────────────────
    if "project_id" not in st.session_state:
        if api_ok:
            pid = get_or_create_project()
            st.session_state.project_id = pid
        else:
            st.session_state.project_id = None

    project_id = st.session_state.get("project_id")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Status")
        if api_ok:
            st.success("✅ Backend connected")
        else:
            st.error("❌ Backend not running")
            st.code("uvicorn app.main:app --reload --port 8000")
            st.stop()

        if project_id:
            st.info(f"Project ID:\n`{project_id[:8]}...`")
        else:
            st.warning("Could not create project — restart backend")
            st.stop()

        st.divider()
        st.header("📄 Upload Documents")
        uploaded = st.file_uploader(
            "Add PDF or TXT to knowledge base",
            type=["pdf", "txt"],
            help="Max 10MB per file",
        )
        if uploaded:
            if st.button("📤 Upload & Index", use_container_width=True):
                with st.spinner(f"Indexing {uploaded.name}…"):
                    result = upload_document(project_id, uploaded)
                    if result:
                        st.success(f"✅ Indexed: {result['filename']}")
                        st.session_state.pop("doc_list", None)

        st.divider()

        # ── Document list ──────────────────────────────────────────────────
        st.header("📚 Indexed Documents")
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.pop("doc_list", None)

        if "doc_list" not in st.session_state:
            st.session_state.doc_list = list_documents(project_id)

        docs = st.session_state.doc_list
        if docs:
            for d in docs:
                size_kb = d["size_bytes"] // 1024
                st.markdown(f"📄 **{d['filename']}** `{size_kb} KB`")
        else:
            st.caption("No documents indexed yet. Upload a PDF above.")

        st.divider()
        st.caption("**Stack:** FastAPI · LlamaIndex · Gemini · S3")

    # ── Chat ──────────────────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                with st.expander(f"📖 {len(msg['citations'])} source(s) | confidence: {msg.get('confidence', 0):.0%}"):
                    for c in msg["citations"]:
                        score_pct = int(c["score"] * 100)
                        st.markdown(
                            f'<div class="citation-box">📄 <b>{c["filename"]}</b> &nbsp;·&nbsp; score: {score_pct}%</div>',
                            unsafe_allow_html=True,
                        )

    # Chat input
    docs_ready = len(st.session_state.get("doc_list", [])) > 0
    placeholder = (
        "Ask a GRC question (e.g. 'What does NIST say about risk assessment?')"
        if docs_ready
        else "Upload a document first, then ask a question…"
    )

    if question := st.chat_input(placeholder):
        # Show user message
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Query and show response
        with st.chat_message("assistant"):
            with st.spinner("Thinking… (first query may take 1–2 min while model loads)"):
                result = query(project_id, question)

            if result:
                answer = result["answer"]
                citations = result.get("citations", [])
                confidence = result.get("confidence", 0.0)
                abstained = result.get("abstained", False)

                if abstained:
                    st.warning(answer)
                else:
                    st.markdown(answer)

                if citations:
                    conf_class = (
                        "confidence-high" if confidence > 0.5 else
                        "confidence-mid" if confidence > 0.2 else
                        "confidence-low"
                    )
                    with st.expander(
                        f"📖 {len(citations)} source(s) · "
                        f"<span class='{conf_class}'>{confidence:.0%} confidence</span>",
                        expanded=False,
                    ):
                        for c in citations:
                            score_pct = int(c["score"] * 100)
                            st.markdown(
                                f'<div class="citation-box">📄 <b>{c["filename"]}</b> &nbsp;·&nbsp; score: {score_pct}%</div>',
                                unsafe_allow_html=True,
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                    "confidence": confidence,
                })


if __name__ == "__main__":
    main()
