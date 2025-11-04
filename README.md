
# SOP Compliance Agent (Mini Project)

## Overview

This project implements a **Risk / InfoSec Access Control Compliance Agent** that answers SOP-based security policy questions with document traceability, JSON decision mode and grounded retrieval.

This application uses:
- **Azure OpenAI**
- **LlamaIndex** for document indexing + retrieval
- **Streamlit** UI with memory, tool calling, decision mode JSON, and chunk traceability

### Purpose
This agent allows teams to ask compliance / access control policy questions and receive answers strictly grounded through the SOP PDF content.

---

## Features Included (Project Requirements Coverage)

| Requirement | Status | Implementation Detail |
|------------|--------|-----------------------|
| Tool Calling | ✅ | Retrieve Policy button shows contextual chunks |
| Memory | ✅ | Session-level conversation memory displayed in UI |
| JSON Decision Mode | ✅ | YES / NO / CONDITIONAL judgment + rationale + citations |
| Doc QA with LlamaIndex | ✅ | SOP PDF ingestion + FAISS vector search |
| Azure AI Integration | ✅ | AzureChatOpenAI used as default LLM |
| Traceability | ✅ | Shows source file name + SOP page + chunk + similarity scores |
| Retry Mechanism | ✅ | JSON parser auto retry when malformed JSON |
| Real SOP grounding | ✅ | Custom Access Control SOP you created + uploaded to docs/ |

---

## Folder Structure

```
mini_project_2_llamaindex_streamlit/
│
├── docs/
├── storage/
├── ingest.py
├── streamlit_app.py
├── decision_schema.py
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1) Create virtual environment

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Add SOP PDFs into /docs folder

### 4) Run App

```powershell
streamlit run streamlit_app.py
```

### 5) Fill Azure Keys from Sidebar UI

---

## Example Questions

- Can a contractor get VPN access for 90 days?
- Can interns access production environments?
- Can I get write access to a production DB?

---

## Decision Mode JSON example

```json
{
  "verdict": "YES",
  "rationale": "Contractors are allowed VPN access up to 90 days with justification.",
  "citations": ["AC-5.1","AC-2.2"]
}
```

---

## Author

Arinjay Jha

