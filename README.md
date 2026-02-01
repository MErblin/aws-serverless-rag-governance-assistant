# 📚 DocuChat RAG

> AI-powered document Q&A using LlamaIndex, FastAPI, and Streamlit — 100% local and free!

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.10+-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🤔 What is DocuChat?

**DocuChat lets you chat with your documents.** Upload any PDF or text file, ask questions in plain English, and get answers based on what's inside your document.

**Example:** Upload a 50-page employee handbook → Ask "What's the vacation policy?" → Get the answer instantly.

**Why use it?**
- 🔒 Runs 100% on your computer (your documents stay private)
- 🆓 No API keys or subscriptions needed
- 📴 Works offline once set up

## ✨ Features

- 📄 **Upload Documents** — Support for PDF and TXT files
- 💬 **Natural Language Q&A** — Ask questions in plain English
- 🔍 **Semantic Search** — Find relevant content using vector embeddings
- 🤖 **Local LLM** — Powered by Ollama (no API keys required!)
- 🚀 **Modern Stack** — FastAPI backend + Streamlit frontend

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────▶│  FastAPI API    │────▶│   LlamaIndex    │
│   (Frontend)    │     │   (Backend)     │     │   (RAG Core)    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┼────────────────────┐
                        │                                │                    │
                        ▼                                ▼                    ▼
                ┌───────────────┐              ┌─────────────────┐   ┌───────────────┐
                │   ChromaDB    │              │   HuggingFace   │   │    Ollama     │
                │ (Vector Store)│              │  (Embeddings)   │   │    (LLM)      │
                └───────────────┘              └─────────────────┘   └───────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** — Download from [ollama.ai](https://ollama.ai)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/docuchat-rag.git
cd docuchat-rag
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Activate it (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (optional)
```

### 4. Install Ollama and Download Model

```bash
# Install Ollama from https://ollama.ai

# Pull the Llama 3.2 model (or your preferred model)
ollama pull llama3.2
```

### 5. Start the Application

**Terminal 1 — Start Ollama:**
```bash
ollama serve
```

**Terminal 2 — Start FastAPI Backend:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 3 — Start Streamlit Frontend:**
```bash
streamlit run ui/app.py --server.port 8501
```

### 6. Open the App

Navigate to [http://localhost:8501](http://localhost:8501) in your browser.

## 📖 API Documentation

Once the backend is running, view the interactive API docs:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/upload` | Upload a document |
| POST | `/api/query` | Query documents |

## 🧪 Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run only unit tests
pytest tests/unit -v

# Run only integration tests
pytest tests/integration -v
```

## 📁 Project Structure

```
docuchat-rag/
├── app/                    # FastAPI Backend
│   ├── api/               
│   │   └── routes.py       # API endpoints
│   ├── services/          
│   │   ├── ingestion.py    # Document processing
│   │   └── rag.py          # RAG query logic
│   ├── config.py           # Configuration
│   └── main.py             # FastAPI app
├── ui/                     
│   └── app.py              # Streamlit frontend
├── tests/                  
│   ├── unit/               # Unit tests
│   └── integration/        # API tests
├── data/                   
│   └── chroma/             # Vector DB storage
├── pyproject.toml          # Dependencies
└── README.md
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| RAG Framework | LlamaIndex |
| Backend | FastAPI |
| Frontend | Streamlit |
| Vector Database | ChromaDB |
| Embeddings | HuggingFace (all-MiniLM-L6-v2) |
| LLM | Ollama (Llama 3.2) |
| Testing | pytest |

## 🗺️ Roadmap

- [x] **Sprint 1:** Project foundation
- [ ] **Sprint 2:** Document ingestion pipeline
- [ ] **Sprint 3:** RAG query engine
- [ ] **Sprint 4:** Complete API
- [ ] **Sprint 5:** UI polish & MVP release

### Future Enhancements

- 📎 Source citations with document excerpts
- 📁 Multi-document management
- 💬 Conversation memory
- 🔐 User authentication
- ☁️ Cloud deployment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ using LlamaIndex, FastAPI, and Streamlit**
