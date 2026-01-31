"""
DocuChat RAG - FastAPI Application

AI-powered document Q&A using LlamaIndex, FastAPI, and Streamlit.
"""

from app.config import get_settings

__version__ = get_settings().app_version
