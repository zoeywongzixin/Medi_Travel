# AI Medical Matching Pipeline

A multi-agent system designed to match patients with medical care, logistics, and financial aid in the ASEAN region.

## 🚀 Current Status

**Logistics & Flight Agent:** ✅ Fully Settled!
- Replaced hardcoded transport files with a centralized `flight_agent.py`.
- Integrated **SerpApi (Google Flights)** to fetch 100% real airline names, dynamic prices, and exact departure/arrival times.
- Implemented intelligent "Stretcher" handling (generates pre-filled Air Ambulance email drafts instead of static prices).
- Built-in "Mock Mode" to save API credits during testing.

## ⚙️ Setup Instructions

### 1. Prerequisites
Ensure you have the following installed on your machine:
- **Python 3.x**
- **Ollama:** Required for the local AI translation and orchestration steps. (Must be running in the background before executing the pipeline).
- **Poppler:** Required for PDF OCR extraction. Make sure `C:\poppler\bin` is properly configured in your system.

### 2. Install Dependencies
Install the required Python packages:
```bash
pip install serpapi python-dotenv
# Add any other required dependencies here or use requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory. You will need a SerpApi key for live flight data:

```env
SERPAPI_KEY=your_serpapi_key_here
```

### 4. Running the Pipeline
Before running, **make sure Ollama is open and running in the background.**

```bash
python main_logic.py
```

## 🛠️ Testing & Saving API Credits (Mock Mode)
SerpApi provides 100 free searches per month. To avoid burning credits while testing other agents (like the Medical or Charity agents):

1. Open your `.env` file.
2. Comment out your SerpApi key by adding a `#`:
   ```env
   #SERPAPI_KEY=your_serpapi_key_here
   ```
3. Run the pipeline. The `flight_agent.py` will automatically detect that the key is missing and fall back to using **Mock Data** (costs 0 credits).
