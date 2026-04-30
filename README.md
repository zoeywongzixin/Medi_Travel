# 🩺 ASEAN Medical AI Matching Backend

A sophisticated multi-layer AI agentic system designed to match international patients (Medical Tourists) with specialized healthcare providers, logistical support, and financial aid in Malaysia.

## 🚀 Latest Improvements — Precision & Regional Logic
We have significantly upgraded the core intelligence of the system with more granular matching and a premium user interface:

- **Enhanced Charity Intelligence**: Now supports specific ASEAN regional groupings like **CLMV** (Cambodia, Laos, Myanmar, Vietnam), **BIMP-EAGA**, and **IMES** for hyper-local financial aid matching.
- **Clinical Reranking v2**: Our AI judge (Ollama) now performs **Sub-Specialty Alignment**, matching granular doctor tags against diagnosis and prioritizing **Tier 1 Hospitals** for critical cases.
- **Age-Aware Orchestration**: Automated detection and logic for Infant, Child, Adult, and Senior patient categories across the entire agentic pipeline.
- **Premium Pipeline Tester**: A completely redesigned, interactive GUI with glassmorphism aesthetics and step-by-step clinical verification.
- **Hybrid Doctor Search**: Merges **Semantic (Vector)** and **Keyword (Token-Overlap)** ranking using **Reciprocal Rank Fusion (RRF)** for high search precision.

## 🧠 AI Architecture & Data Layers

Our system is built as a **Multi-Layer Agentic Orchestrator**. Each layer uses specific AI tools to ensure accuracy and transparency.

### Layer 1: Medical Specialist Matching (Precision Engine)
*   **AI Tools**: **Ollama (Llama 3.2:3b)** + **ChromaDB (Hybrid RAG)**.
*   **Enriched Logic**:
    *   **Sub-Specialty Alignment**: Matches doctor "specialty tags" (e.g., *Robotic Urology*) directly against patient diagnosis.
    *   **Hospital Tiers**: Critical cases are prioritized for Tier 1 specialized centers (advanced technology & higher care).
    *   **Age-Group Context**: Reranking logic adjusts based on the patient's age (Paediatric vs. Geriatric expertise).
    *   **Urgency Boost**: High-urgency cases favor senior consultants with Full Registration status.

### Layer 2: Logistics & Flight Intelligence
*   **AI Tools**: **Official SerpApi Client** + **Logistic Reasoning Engine**.
*   **How it Works**: 
    1.  Analyzes the patient's medical chart to determine mobility (Ambulatory vs. Stretcher).
    2.  Fetches **LIVE flight data** or generates a **Medical Charter Email Draft** based on transport needs.

### Layer 3: Financial Aid & Charity Matching (Regional RAG)
*   **AI Tools**: **Semantic Vector Matching** + **ASEAN Regional Logic**.
*   **Regional Groupings**: Explicit logic for **CLMV**, **BIMP-EAGA**, and **IMES** groupings to prioritize funds originating from or targeting the patient's sub-region.
*   **Strict Scope**: Focused on **Oncology** and **Cardiology** high-cost surgical cases.

---

## 🛠️ Project Structure
- `agents/`: Core multi-agent logic (`medical_agent.py`, `rerank_agent.py`, `flight_agent.py`, `charity_agent.py`).
- `pipeline/`: Data ingestion and vectorization logic.
- `tests/`: 
  - `pipeline_tester.html`: New premium GUI tool for interactive pipeline verification.
  - `test_charity_rag.py`: Tests for regional and country-priority matching.
- `docker-compose.yml`: Fully containerized orchestration with Ollama and ChromaDB.

---

## ⚙️ How to Run

### 1. Start via Docker (Recommended)
This will automatically pull the AI models and ready the medical database:
```powershell
docker-compose up --build
```

### 2. Test in Browser
Access the interactive pipeline tester at:
`http://localhost:8000/tester` (or open `tests/pipeline_tester.html` directly).

---

## 🤖 AI Assistant Contribution
This project was developed and refined in collaboration with **Antigravity**, an advanced agentic AI coding assistant designed by Google Deepmind. Key contributions include:
- Implementing the **Hybrid Search Engine (RRF)** for doctor matching.
- Developing the **ASEAN Sub-Regional logic** for the Charity Agent.
- Creating the **Premium Pipeline Tester UI** with Age-Group and Clinical Tag support.
- Orchestrating the multi-stage LLM reranking and package combination logic.

---
**Build for ASEAN AI Hackathon 2026**
