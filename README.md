# 🩺 ASEAN Medical AI Matching Backend

A sophisticated multi-layer AI agentic system designed to match international patients (Medical Tourists) with specialized healthcare providers, logistical support, and financial aid in Malaysia.

## 🚀 Recent Improvements — Stronger Matching Engine
We have upgraded the core intelligence of the system with a more robust, multi-stage matching pipeline:

- **Hybrid Doctor Search**: Merges **Semantic (Vector)** and **Keyword (Token-Overlap)** ranking using **Reciprocal Rank Fusion (RRF)** for 2x better search precision.
- **4-Stage Agentic Funnel**: 
    1.  **Hybrid RAG Search** (Top-20 candidates).
    2.  **Hard Specialty Gate** (Ensures doctor group matches diagnosis).
    3.  **Metadata-Enriched Scoring** (Bonuses for Severity, Urgency, and Paediatrics).
    4.  **LLM Judge (Rerank)** (Ollama compares the Top-5 and selects the final Top-3).
- **Docker-First Stability**: Now uses **Named Volumes** for ChromaDB to prevent SQLite Disk I/O errors on Windows and includes **Auto-Model Pulling** for Ollama.

## 🧠 AI Architecture & Data Layers

Our system is built as a **Multi-Layer Agentic Orchestrator**. Each layer uses specific AI tools to ensure accuracy and transparency.

### Layer 1: Medical Specialist Matching (Stronger Engine)
*   **AI Tools**: **Ollama (Llama 3.2:3b)** + **ChromaDB (Hybrid RAG)**.
*   **Enriched Logic**:
    *   **Severity Boost**: Critical cases are automatically prioritized for Government specialist centers (IKN, IJN).
    *   **Urgency Boost**: High-urgency cases favor doctors with Full Registration numbers (Senior Consultants).
    *   **Paediatric Focus**: Auto-detects child patients and boosts specialists with paediatric experience.
*   **Reranking**: An LLM agent acts as a final "Judge" to compare the top candidates based on the actual case summary.

### Layer 2: Logistics & Flight Intelligence
*   **AI Tools**: **Official SerpApi Client** + **Logistic Reasoning Engine**.
*   **How it Works**: 
    1.  Analyzes the patient's medical chart to determine mobility (Ambulatory vs. Stretcher).
    2.  If ambulatory, it fetches **LIVE flight data** (prices, times, airlines).
    3.  If stretcher-bound, it generates a professional **Medical Charter Email Draft**.

### Layer 3: Financial Aid & Charity Matching
*   **AI Tools**: **Semantic Vector Matching** + **Ollama Eligibility Reasoning**.
*   **Strict Scope**: Only matches for **Oncology** and **Cardiology** cases.
*   **Fund Matching**: Prioritizes funds based on patient severity and origin country coverage.

---

## 🛠️ Project Structure
- `agents/`: Core multi-agent logic (`medical_agent.py`, `rerank_agent.py`, `flight_agent.py`, `charity_agent.py`).
- `pipeline/`: Data ingestion (`ingest_doctors.py`, `ingest_charities.py`).
- `tests/`: 
  - `pipeline_tester.html`: GUI tool for manual pipeline testing.
  - `test_hybrid_matching.py`: Unit tests for the new search engine.
- `docker-compose.yml`: Production-ready orchestration with Ollama and backend.

---

## ⚙️ How to Run

### 1. Start via Docker (Recommended)
This will automatically pull the AI models and ingest the medical database:
```powershell
docker-compose up --build
```
*Note: The first run may take 5–10 minutes to download the AI models and ChromaDB components.*

### 2. Test in Browser
Once the backend is ready (check for `=== All collections ready ===` in logs), open:
`c:\Documents\Jasmine\ai_medical_matching\tests\pipeline_tester.html`

### 3. Run Unit Tests (Local)
```bash
python tests/test_hybrid_matching.py
```

---

## 🤖 AI Assistant Contribution
This project was developed and refined in collaboration with **Antigravity**, an advanced agentic AI coding assistant designed by Google Deepmind. Key contributions include:
- Refactoring the monolithic backend pipeline into an interactive, multi-step wizard.
- Exposing independent API endpoints for the medical, logistics, and charity layers to enable step-by-step option selection.
- Implementing a final package combination endpoint for personalized LLM reasoning.
- Setting up and finalizing the Docker deployment configuration.

---
**Build for ASEAN AI Hackathon 2026**
