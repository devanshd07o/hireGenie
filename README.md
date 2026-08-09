# 🤖 HireGenie — AI Technical Interview Agent (Backend & API)

**Hackathon Project — "The AI Cohort" 31-Day AI Engineering Curriculum**

HireGenie is a production-quality, SaaS-style backend + REST API for an **AI Technical Interview Agent**. It conducts realistic, multi-turn, adaptive technical interviews for candidates based on a 31-day AI curriculum and candidate profiles (completed topics, skipped topics, attempts, learning signals).

---

## 🌟 Key Features

1. **Adaptive Multi-Turn Technical Interviewing**:
   - Asks practical, applied technical questions tailored to the candidate's completed curriculum topics.
   - Dynamically evaluates answers: asks targeted follow-ups if an answer is shallow/incomplete, or advances to the next topic if the answer is strong.
   - Covers at least 4 curriculum days and maintains conversation memory across turns.
2. **Multi-Provider LLM Fallback System (100% Free Tier)**:
   - **Provider 1**: Google Gemini (`gemini-2.0-flash`)
   - **Provider 2**: Groq (`llama-3.3-70b-versatile`)
   - **Provider 3**: OpenRouter (`free-tier models`)
   - **Safety Net**: Built-in fallback mock engine so the app **never crashes** even if API keys are missing or quota limit is reached.
3. **Structured Performance Evaluation**:
   - Generates structured JSON feedback at the end of the interview:
     - Overall summary
     - Key strengths & areas for improvement
     - Topic-by-topic assessment (`strong`, `moderate`, `weak`)
     - Readiness Signal (`Ready`, `Needs Practice`, `Not Ready`)
4. **SaaS-Style Data Management**:
   - Manage Candidates (`GET`, `POST`, `DELETE /candidates`)
   - Manage Curriculum (`GET`, `POST`, `DELETE /curriculum`)
   - View Session History & Transcripts (`GET /interview/session/{session_id}`)
5. **Zero-Setup Database**:
   - Uses SQLite file-based DB (`hiregenie.db`). Automatically seeds 31-day curriculum (`data/curriculum.json`) and realistic candidate profiles (`data/candidates.json`) on startup.
6. **Cross-Origin Ready (CORS Enabled)**:
   - Configured with `fastapi.middleware.cors` for seamless integration with Flutter Web or React frontends.

---

## 🏗 System Architecture

```
HireGenie Backend Architecture
├── data/
│   ├── curriculum.json         # 31-Day AI Cohort curriculum dataset
│   └── candidates.json         # Mock candidate profiles (completed/skipped topics, signals)
├── database.py                 # SQLite database engine & SQLAlchemy session setup
├── models.py                   # Pydantic schemas & SQLAlchemy ORM models
├── llm_service.py              # Multi-Provider Fallback Layer (Gemini -> Groq -> OpenRouter -> Fallback)
├── interview_logic.py          # Adaptive prompting, question sequencing & JSON evaluation logic
├── main.py                     # FastAPI REST API endpoints, CORS, auto-seeding & docs
├── test_interview.py           # Automated integration test script for all endpoints
├── requirements.txt            # Production dependencies
├── Procfile                    # Render / Railway deployment configuration
└── README.md                   # Full documentation
```

---

## ⚡ Quickstart Guide

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/your-username/HireGenie.git
cd HireGenie

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and add your free API keys (optional — if omitted, the fallback engine handles requests smoothly):

```env
GEMINI_API_KEY=your_google_ai_studio_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key
```

### 4. Run Server Locally

```bash
uvicorn main:app --reload --port 8001
```

Open your browser at **[http://localhost:8001/docs](http://localhost:8001/docs)** to view the interactive OpenAPI Swagger UI.

---

## 🧪 Running Automated Integration Tests

To run the automated integration test suite that tests candidate loading, curriculum retrieval, interview session creation, multi-turn messages, and JSON feedback generation:

```bash
python test_interview.py
```

---

## 📡 REST API Reference

### 1. Health Check
- `GET /` : Returns API health status.

### 2. Interview Operations
- `POST /interview/start`
  - **Body**: `{"candidate_id": "cand_001"}`
  - **Response**: `session_id`, `first_question`, candidate metadata, target curriculum days.
- `POST /interview/message`
  - **Body**: `{"session_id": "<UUID>", "answer": "<candidate's text answer>"}`
  - **Response**: `next_question`, `is_followup`, current progress.
- `POST /interview/end`
  - **Body**: `{"session_id": "<UUID>"}`
  - **Response**: Full structured JSON feedback (summary, strengths, weaknesses, topic breakdown, readiness signal).
- `GET /interview/session/{session_id}`
  - Returns complete transcript history, status, and feedback object.

### 3. Candidate SaaS Management
- `GET /candidates` : List all candidates.
- `POST /candidates` : Add a new candidate profile.
- `DELETE /candidates/{candidate_id}` : Delete a candidate profile.

### 4. Curriculum SaaS Management
- `GET /curriculum` : List 31-day curriculum topics.
- `POST /curriculum` : Add a curriculum day.
- `DELETE /curriculum/{day}` : Delete a curriculum day.

---

## 🚀 Cloud Deployment (Render / Railway / Fly.io)

This repository includes a `Procfile` for cloud deployment:

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Render Deployment Steps:
1. Connect your repository to **Render** as a **Web Service**.
2. Environment: `Python 3`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables (`GEMINI_API_KEY`, etc.) in the Render dashboard.

---

## 📜 License & Credits

Built for **The AI Cohort Hackathon (Problem Statement 2)**. Designed as a production-grade AI Interview Agent backend service for seamless integration with Flutter Web.
