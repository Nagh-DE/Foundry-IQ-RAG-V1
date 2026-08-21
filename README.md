# Foundry IQ RAG — Health & Banking

A production RAG system built on **Azure AI Foundry IQ** (Knowledge Base + Knowledge Sources) with a FastAPI backend. Queries span FDIC banking data, FRED economic indicators, and healthcare research PDFs — all from a single `/chat` endpoint.

## Architecture

```
Azure SQL (13 tables)  ──┐
Azure Blob (12 PDFs)   ──┼──► Knowledge Sources ──► Knowledge Base (health-banking-kb)
                          │                                  │
                          └──────────────────────────────────┘
                                                             │
                                          FastAPI /chat ─────┤
                                                             │
                                   KnowledgeBaseRetrievalClient (extractiveData)
                                                             │
                                        OpenAI chat.completions (synthesis)
                                                             │
                                                          Answer
```

## Data Sources

| Source | Type | Content |
|--------|------|---------|
| `fdic_institutions` | Azure SQL | FDIC-insured bank institutions |
| `fdic_locations` | Azure SQL | Bank branch locations |
| `fdic_financials` | Azure SQL | Bank financial reports (ROA, ROE) |
| `fred_fedfunds` | Azure SQL | Federal Funds Rate time series |
| `fred_cpi` | Azure SQL | Consumer Price Index |
| `fred_gdp` | Azure SQL | US GDP |
| `fred_unemployment` | Azure SQL | Unemployment Rate |
| `fred_mortgage` | Azure SQL | 30-Year Fixed Mortgage Rate |
| `fred_health_spending` | Azure SQL | Health Care Expenditures |
| `my-blob-ks-2` | Azure Blob | 12 health/banking research PDFs |

## Setup

### Prerequisites

- Azure AI Foundry project with a deployed LLM (`gpt-4.1`) and embedding model (`text-embedding-3-small`)
- Azure AI Search service
- Azure SQL Database with Change Tracking enabled
- Azure Blob Storage container
- `az login` completed (used by `DefaultAzureCredential` at runtime)

### 1. Clone and install

```bash
git clone https://github.com/Nagh-DE/Foundry-IQ-RAG-V1.git
cd Foundry-IQ-RAG-V1
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your values in .env
```

### 3. Load data into Azure SQL

```bash
python load_to_sql.py
```

### 4. Create Knowledge Sources and Knowledge Base

Run the notebooks in order:

```
notebooks/knowledge-source.ipynb   # creates 13 SQL + blob knowledge sources
notebooks/knowledge-base.ipynb     # creates health-banking-kb
```

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

## API

### `POST /chat`

```json
// Request
{
  "question": "Which banks are headquartered in Texas?",
  "conversation_id": null
}

// Response
{
  "answer": "Based on the knowledge base...",
  "conversation_id": "3f8a2b1c-...",
  "sources": [
    { "type": "indexedSql", "id": "0", "reranker_score": 2.41, "blob_url": null }
  ]
}
```

Pass `conversation_id` from the previous response to continue a multi-turn conversation.

### `GET /health`

```json
{ "status": "ok", "kb": "health-banking-kb", "model": "gpt-4.1" }
```

## Project Structure

```
app/
├── main.py              FastAPI app, lifespan, CORS
├── config.py            Pydantic settings (reads .env)
├── schemas.py           Request / response models
├── services/
│   └── kb.py            KBService: retrieval + synthesis + conversation history
└── routers/
    └── chat.py          POST /chat

notebooks/
├── knowledge-source.ipynb    Create SQL + blob knowledge sources
├── knowledge-base.ipynb      Create / update health-banking-kb
└── agent-kb.ipynb            Interactive KB querying (dev / testing)

load_to_sql.py           Bulk-load CSV files into Azure SQL
```

## How It Works

1. **Retrieval** — `KnowledgeBaseRetrievalClient.retrieve()` sends the question to `health-banking-kb` with `output_mode="extractiveData"`. The knowledge base ranks and returns raw document chunks from whichever sources are most relevant — no LLM call at this step.

2. **Synthesis** — the ranked chunks are passed as context to `openai_client.chat.completions.create()`. The LLM reads the chunks and writes a grounded answer.

3. **Multi-turn** — conversation history is stored in-memory per `conversation_id`. Pass the same ID on follow-up questions to maintain context.
