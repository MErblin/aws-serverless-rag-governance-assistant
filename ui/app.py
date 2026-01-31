"""
DocuChat RAG - Streamlit UI

User interface for document upload and Q&A interaction.
"""

import streamlit as st
import requests
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000/api"

# Page configuration
st.set_page_config(
    page_title="DocuChat RAG",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def check_api_health() -> bool:
    """Check if the FastAPI backend is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def upload_document(file) -> Optional[dict]:
    """Upload a document to the API."""
    try:
        files = {"file": (file.name, file.getvalue(), file.type)}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Upload failed: {response.json().get('detail', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")
        return None


def query_documents(question: str) -> Optional[dict]:
    """Send a query to the API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={"question": question},
            timeout=60,
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Query failed: {response.json().get('detail', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {e}")
        return None


def main():
    """Main Streamlit application."""
    
    # Header
    st.title("📚 DocuChat RAG")
    st.markdown("*AI-powered document Q&A using LlamaIndex*")
    
    # Sidebar
    with st.sidebar:
        st.header("📁 Document Upload")
        
        # API Status
        api_healthy = check_api_health()
        if api_healthy:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Not Available")
            st.info("Start the backend with: `uvicorn app.main:app --reload`")
        
        st.divider()
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Upload a document",
            type=["pdf", "txt"],
            help="Supported formats: PDF, TXT (max 10MB)",
        )
        
        if uploaded_file is not None:
            if st.button("📤 Process Document", use_container_width=True):
                with st.spinner("Processing document..."):
                    result = upload_document(uploaded_file)
                    if result:
                        st.success(f"✅ {result['message']}")
                        st.info(f"Document ID: {result['document_id']}")
        
        st.divider()
        st.markdown("### About")
        st.markdown(
            """
            DocuChat uses RAG (Retrieval-Augmented Generation) to answer
            questions based on your uploaded documents.
            
            **Tech Stack:**
            - 🦙 LlamaIndex
            - ⚡ FastAPI
            - 🎈 Streamlit
            - 🗄️ ChromaDB
            - 🤖 Ollama
            """
        )
    
    # Main chat area
    st.header("💬 Ask a Question")
    
    # Initialize chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if question := st.chat_input("Ask a question about your documents..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        
        # Get response from API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = query_documents(question)
                if result:
                    answer = result["answer"]
                    st.markdown(answer)
                    
                    # Show sources if available
                    if result.get("sources"):
                        with st.expander("📖 Sources"):
                            for source in result["sources"]:
                                st.markdown(f"- {source}")
                    
                    # Add assistant message to chat
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )
                else:
                    error_msg = "Sorry, I couldn't process your question."
                    st.error(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )


if __name__ == "__main__":
    main()
