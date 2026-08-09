# HireGenie Pro — AI Usage Log (PROMPTS.md)

> This file documents the AI prompting strategy, LLM usage, and vibe-coding process behind HireGenie Pro.

---

## 🤖 AI Providers Used

| Provider | Model | Role |
|---|---|---|
| **Groq** | Llama-3.3-70B-Versatile | Primary interviewer — fast Q&A generation |
| **Google Gemini** | Gemini-2.0-Flash | Fallback — complex reasoning & evaluation |
| **Cerebras** | Llama-3.3-70B | Ultra-fast secondary fallback |
| **OpenRouter** | Meta Llama 3.3 70B | Final fallback layer |
| **Sarvam AI** | — | Regional language support |

---

## 🧠 Core AI Prompting Strategy

### 1. Interview Session Prompt (System)

```
You are HireGenie — a world-class Senior Technical Interviewer conducting a rigorous, professional technical assessment.

ROLE & BEHAVIOR:
- Ask ONE focused, practical applied engineering question at a time (system design trade-offs, debugging, edge cases, real-world scenarios). NO textbook definitions.
- If the previous answer was shallow/incomplete: ask a sharp, targeted follow-up digging into specifics.
- If the answer was strong: briefly acknowledge (1 sentence max) then move to the next topic.
- Stay within the scope of the provided course curriculum/topics only.
- Keep questions concise (2-3 sentences max per question).
- Maintain a professional, encouraging, sharp tone.
- Do NOT reveal scoring or evaluation during the interview.
```

### 2. Session Start Prompt

```
You are starting a technical interview with {candidate_name}.

Course/Curriculum Context:
{course_context}

Begin the interview: warmly introduce yourself as HireGenie AI Interviewer, state the candidate's name, and ask your FIRST practical technical question based on the curriculum topics above.
```

### 3. Evaluation / Scorecard Prompt

```
You are the Lead Technical Evaluator. Based on this complete interview transcript, generate a comprehensive candidate assessment.

Return ONLY valid JSON with:
- overall_summary: 2-3 paragraph comprehensive performance summary
- strengths: list of key strengths demonstrated
- weaknesses: list of areas needing improvement
- topic_breakdown: per-topic assessment (strong/moderate/weak)
- readiness_signal: Ready | Needs Practice | Not Ready
- radar_scores: competency scores (0-100) across 6 dimensions
```

---

## 🔄 Multi-Tier LLM Fallback Pipeline

```
Request → Groq (Llama-3.3-70B) → [fail] → Gemini 2.0 Flash → [fail] → Cerebras → [fail] → OpenRouter → [fail] → Static Fallback
```

Every single AI response in HireGenie is 100% LLM-generated — no hardcoded strings, no fake placeholders.

---

## 📊 AI-Powered Features

1. **Adaptive Questioning** — AI decides follow-up vs new topic based on answer quality
2. **Curriculum-Aware** — AI reads full 31-day JSON curriculum before each interview
3. **Custom JSON Curriculum** — Upload any JSON, AI extracts topics automatically
4. **Structured Evaluation** — AI generates JSON scorecards with radar chart scores
5. **Real-time Tag Generation** — AI classifies each response (Follow-up / Topic Transition / New Topic)

---

## 🏗️ Vibe-Coded With

- **Antigravity AI (Google DeepMind)** — Full-stack agentic coding assistant
- Every file in this repo was built through natural language prompting
- Backend, API design, DB schema, UI, deployment config — all AI-generated

---

## 📁 Key AI-Driven Files

- [`main.py`](./main.py) — All interview API endpoints, fully LLM-powered
- [`llm_service.py`](./llm_service.py) — Multi-provider LLM orchestration engine
- [`static/index.html`](./static/index.html) — Frontend, every chat turn powered by AI
- [`data/curriculum.json`](./data/curriculum.json) — 31-day AI Cohort curriculum fed to LLM
