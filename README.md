# ASEAN Medical Match

ASEAN Medical Match is a multi-agent medical travel matching platform for patients seeking treatment in Malaysia. It combines clinical extraction, hospital matching, flight planning, charity matching, and visa-support document generation in one workflow.

## What is new

- Country-first onboarding with ASEAN flag selection
- Simpler UI focused on one guided patient flow
- Localized interface based on the selected country
- Translated recommendation text and translated PDF support letters
- Structured MHTC / Borang IM.47 visa support letters with placeholder-only PII
- Clinical extraction that now explicitly tracks age group and urgency

## User flow

1. Open the app at `/tester`
2. Choose an ASEAN country from the flag list
3. The app switches to that country's language for the UI
4. Upload a medical report image or PDF
5. Review extracted clinical fields:
   - Age Group
   - Diagnosis
   - Urgency Status
6. Select one hospital, one flight, and one charity
7. Generate the final itinerary and download support letters

## Current letter behavior

The visa-support flow is deterministic and formatted for `fpdf2` `multi_cell(...)` usage.

- The letter includes:
  - clinical extraction summary
  - selected hospital
  - selected flight
  - selected charity
  - MHTC and Borang IM.47 references
- Personal identifiers are never injected into the visa-support content
- PII fields are emitted as literal blanks:
  - `PATIENT NAME: ___________________________`
  - `PASSPORT NUMBER: _______________________`
  - `CAREGIVER NAME: _________________________`
- If the case is `Critical`, the tone changes to a medical appeal
- Otherwise, it stays a medical travel support letter

## Architecture

```mermaid
flowchart TB
    subgraph Client["Multilingual Client (Next.js/HTML)"]
        UI["ASEAN Flag Selection<br/>& Medical Report Upload"]
    end

    subgraph API_Gateway["FastAPI Backend Gateway"]
        E_API["/extract"]
        M_API["/match-*"]
        P_API["/combine-package"]
        L_API["/generate-letter"]
    end

    subgraph Layer1["Layer 1: AI Clinical Extraction"]
        direction TB
        OCR["OCR Engine<br/>(PaddleOCR/EasyOCR)"] --> Scrub["PII Scrubbing<br/>(Deterministic)"]
        Scrub --> Trans["Medical Translation<br/>(Llama 3.2)"]
        Trans --> Parse["Clinical Parsing<br/>(Llama 3.2 JSON)"]
    end

    subgraph Layer2["Layer 2: Hospital Matching Agent"]
        direction TB
        ChromaM[("Medical Vector Store<br/>(ChromaDB)")] --> Sem["Semantic Retrieval"]
        Sem --> Key["Keyword Fusion<br/>(BM25-style)"]
        Key --> Score["Metadata-Enriched<br/>Scoring"]
        Score --> Judge["AI Medical Judge<br/>(Llama 3.2 Rerank)"]
    end

    subgraph Layer3["Layer 3: Logistics & Charity Agents"]
        direction LR
        Logistics["Mobility-Aware<br/>Transport Matcher"]
        Charity["2-Stage RAG<br/>Charity Matcher"]
    end

    subgraph Layer4["Layer 4: AI Package Orchestrator"]
        ORCH["Package Synthesis"]
        Reason["AI Reasoning<br/>(Personalized Itinerary)"]
        ORCH --- Reason
    end

    subgraph Layer5["Layer 5: Documentation & Localization"]
        PDF["PDF Generation<br/>(fpdf2)"]
        Loc["Localized Templates<br/>(Indonesian, Thai, etc.)"]
    end

    UI --> E_API
    E_API --> Layer1
    Layer1 --> M_API
    M_API --> Layer2 & Layer3
    Layer2 & Layer3 --> P_API
    P_API --> Layer4
    Layer4 --> L_API
    L_API --> Layer5

    %% Styling
    classDef ai_component fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b;
    classDef db_component fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100;
    classDef core_component fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#4a148c;

    class Trans,Parse,Judge,Reason ai_component;
    class ChromaM,ChromaC db_component;
    class ORCH,OCR,PDF core_component;
```

### AI Integration Details

ASEAN Medical Match utilizes a multi-agent AI architecture powered by **Llama 3.2** (via Ollama) and **ChromaDB**:

*   **AI Clinical Extraction**: Uses LLMs to translate diverse ASEAN medical reports into English and extract structured clinical parameters (Condition, Severity, Urgency) while maintaining PII safety.
*   **AI Medical Judge**: A specialized Rerank Agent that acts as a clinical coordinator, comparing the top 5 semantic hospital matches and re-ordering them based on sub-specialty alignment and hospital tiering.
*   **AI Package Orchestration**: Synthesizes disparate data (Medical, Logistics, Charity) into a cohesive travel itinerary with AI-generated reasoning that explains the value proposition to the patient.
*   **Dynamic Localization**: Real-time translation of both the user interface and generated PDF support letters, ensuring patients receive guidance in their native language.

### Layer 1: Clinical extraction

- OCR extracts raw chart text
- The chart is translated to English for internal parsing
- The parser extracts:
  - condition
  - sub-specialty inference
  - severity
  - age group
  - urgency

### Layer 2: Hospital matching

- ChromaDB semantic retrieval plus keyword fusion
- Specialty-group filtering
- Metadata-aware ranking
- LLM reranking for final specialist recommendations

### Layer 3: Flight and logistics matching

- Mobility-aware transport recommendations
- Commercial flight suggestions for standard cases
- Charter escalation path for stretcher cases

### Layer 4: Charity matching

- Two-stage RAG matching
- Country-priority and ASEAN regional logic
- Focused support for oncology and cardiology use cases

### Layer 5: Documentation

- PDF generation with `fpdf2`
- Country-selected translation for user-facing letters
- Placeholder-safe translation preserving blank PII lines

## Multilingual behavior

The selected country drives:

- interface language
- dynamic recommendation translation
- generated support-letter language

Current frontend language mappings include:

- Brunei -> Malay
- Cambodia -> Khmer
- Indonesia -> Indonesian
- Laos -> Lao
- Malaysia -> Malay
- Myanmar -> Burmese
- Philippines -> Filipino
- Singapore -> English
- Thailand -> Thai
- Vietnam -> Vietnamese

## Key routes

- `GET /` - health check
- `GET /tester` - main user interface
- `POST /api/v1/extract` - OCR, translation, structured clinical extraction
- `POST /api/v1/match-hospitals` - hospital / specialist matches
- `POST /api/v1/match-flights` - flight and transport options
- `POST /api/v1/match-charities` - charity matches
- `POST /api/v1/combine-package` - final package reasoning
- `POST /api/v1/generate-letter` - PDF letter generation
- `POST /api/v1/translate-template` - template translation
- `POST /api/v1/translate-text` - general UI / recommendation translation

## Project structure

- `app.py` - FastAPI entrypoint and API routes
- `agents/` - hospital, flight, charity, logistics, and orchestration logic
- `utils/` - OCR helpers, parser, translator, letter generator
- `frontend/pipeline_tester.html` - country-first multilingual UI served at `/tester`
- `tests/pipeline_tester.html` - mirrored UI file for local reference
- `pipeline/` - ingestion and report-generation scripts
- `data/` - ChromaDB storage

## Run locally with Docker

```powershell
docker-compose up --build
```

Then open:

- [http://localhost:8000/tester](http://localhost:8000/tester)

## Notes

- The backend translates uploaded charts into English for internal extraction, even when the user-facing UI is localized.
- The served UI now lives in `frontend/` so Docker includes it reliably.
- Charity matching currently targets oncology and cardiology support paths.

## Build context

Built for ASEAN medical-travel coordination and hackathon-style rapid matching workflows.
