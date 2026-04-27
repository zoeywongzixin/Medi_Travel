# 🩺 ASEAN Medical AI Matching Backend

A sophisticated multi-layer AI agentic system designed to match international patients (Medical Tourists) with specialized healthcare providers, logistical support, and financial aid in Malaysia.

## 🚀 Recent Improvements
- **Browser-Based Tester**: Added `pipeline_tester.html` for easy one-click testing of the full API flow.
- **Strict Charity Narrowing**: Updated the Charity RAG database to focus exclusively on **Oncology** and **Cardiology**.
- **Enhanced Reliability**:
  - Upgraded to the **Official SerpApi Python Client** for more reliable flight data.
  - Added support for **Ollama 0.4.x** response formats across all agents.
  - Fixed Unicode encoding issues for Windows terminals.

## 🧠 AI Architecture & Data Layers

Our system is built as a **Multi-Layer Agentic Orchestrator**. Each layer uses specific AI tools to ensure accuracy and transparency.

### Layer 1: Medical Specialist Matching
*   **AI Tools**: **Ollama (Llama 3.2:3b)** + **ChromaDB (Vector RAG)**.
*   **How it Works**: 
    1.  The **Medical Agent** uses LLM reasoning to infer the specific sub-specialty needed (e.g., "Electrophysiology" from a general heart report).
    2.  It performs a **Semantic Search** against our centralized Doctor RAG database.
*   **Data Retrieval**: Real-time retrieval from the `malaysia_doctors` vector collection.

### Layer 2: Logistics & Flight Intelligence
*   **AI Tools**: **Official SerpApi Client** + **Logistic Reasoning Engine**.
*   **How it Works**: 
    1.  Analyzes the patient's medical chart to determine mobility (Ambulatory vs. Stretcher).
    2.  If the patient is ambulatory, it fetches **LIVE flight data** (prices, times, airlines).
    3.  If the patient requires a stretcher, it automatically generates a professional **Medical Charter Email Draft**.

### Layer 3: Financial Aid & Charity Matching
*   **AI Tools**: **Ollama (Eligibility Reasoning)** + **Country-Priority Ranking**.
*   **How it Works**: 
    1.  Matches the patient's origin and condition against Malaysian NGO rules.
    2.  **Strict Scope**: Only matches for **Oncology** and **Cardiology** cases.
    3.  **Regional Priority**: Favors regional ASEAN funds (e.g., specific aids for Laos/Vietnam patients).

---

## 🛠️ Project Structure
- `app.py`: Main FastAPI entry point.
- `agents/`: Core multi-agent logic (Medical, Flight, Logistics, Charity, Orchestrator).
- `pipeline/`: Data ingestion and report generation tools.
- `reports/`: Stores visual dashboards (`db_dashboard.html`, `charity_dashboard.html`).
- `tests/`: 
  - `pipeline_tester.html`: GUI tool for manual pipeline testing.
  - `fixtures/`: Mock medical reports (images/txt) for testing.
  - `dev_tools/`: Connection check and DB debugging scripts.
- `utils/`: Shared utilities (OCR, Translation, PII Scrubbing).
- `data/`: Local storage for ChromaDB.

---

## ⚙️ How to Run & Test

### 1. Start the Backend
```bash
python app.py
```

### 2. Test in Browser
Double-click `tests/pipeline_tester.html` in your file explorer.

### 3. Generate Visual Dashboards
```bash
python pipeline/generate_report.py
python pipeline/generate_charity_dashboard.py
```

### 4. Integration Tests
```bash
python tests/test_vietnamese_flow.py
```

---
**Build for ASEAN AI Hackathon 2026**
