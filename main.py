import os
import json
import uuid
import datetime
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HireGenie")

# ─── DATABASE SETUP ────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hiregenie.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CandidateDB(Base):
    __tablename__ = "candidates"
    candidate_id = Column(String, primary_key=True, index=True)
    name = Column(String)
    completed_days = Column(JSON, default=list)
    skipped_days = Column(JSON, default=list)
    attempts = Column(JSON, default=dict)
    learning_signals = Column(JSON, default=dict)

class CurriculumDayDB(Base):
    __tablename__ = "curriculum_days"
    day = Column(Integer, primary_key=True)
    module = Column(String)
    topic = Column(String)
    learning_objectives = Column(JSON, default=list)
    tools_used = Column(JSON, default=list)
    difficulty = Column(String, default="intermediate")

class InterviewSessionDB(Base):
    __tablename__ = "interview_sessions"
    session_id = Column(String, primary_key=True)
    candidate_name = Column(String)
    course_context = Column(Text)          # custom JSON or standard curriculum name
    history = Column(JSON, default=list)   # full conversation log
    status = Column(String, default="active")
    question_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class EvaluationDB(Base):
    __tablename__ = "evaluations"
    session_id = Column(String, primary_key=True)
    candidate_name = Column(String)
    readiness_signal = Column(String)
    overall_summary = Column(Text)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    topic_breakdown = Column(JSON, default=list)
    radar_scores = Column(JSON, default=dict)
    total_questions = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed():
    db = SessionLocal()
    try:
        if db.query(CurriculumDayDB).count() == 0:
            curr_path = os.path.join(os.path.dirname(__file__), "data", "curriculum.json")
            if os.path.exists(curr_path):
                with open(curr_path, encoding="utf-8") as f:
                    for item in json.load(f):
                        db.add(CurriculumDayDB(**item))
                db.commit()
        if db.query(CandidateDB).count() == 0:
            cand_path = os.path.join(os.path.dirname(__file__), "data", "candidates.json")
            if os.path.exists(cand_path):
                with open(cand_path, encoding="utf-8") as f:
                    for c in json.load(f):
                        db.add(CandidateDB(**c))
                db.commit()
    except Exception as e:
        logger.error(f"Seed error: {e}")
    finally:
        db.close()

# ─── FASTAPI SETUP ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    seed()
    yield

app = FastAPI(title="HireGenie Pro API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", tags=["UI"])
def root():
    idx = os.path.join(static_dir, "index.html")
    return FileResponse(idx) if os.path.exists(idx) else {"status": "online"}

# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    candidate_name: str
    course_context: str   # Either "31-Day AI Cohort" or raw JSON string of custom curriculum

class ChatRequest(BaseModel):
    session_id: str
    user_message: str

class EndSessionRequest(BaseModel):
    session_id: str

class CandidateCreate(BaseModel):
    candidate_id: str
    name: str
    completed_days: List[int] = []
    skipped_days: List[int] = []
    attempts: Dict[str, int] = {}
    learning_signals: Dict[str, str] = {}

INTERVIEWER_SYSTEM = """You are HireGenie — a Senior Principal Software Engineer at a top tech company conducting a 1-on-1 technical interview.

DYNAMIC TOPIC ROTATION & METHODOLOGY:
- Talk naturally like an experienced, friendly senior engineer having a collaborative technical conversation.
- DYNAMIC TOPIC PIVOTING: Do NOT get stuck on a single topic! After 1-2 questions on a topic, actively move to a DIFFERENT topic from the candidate's course curriculum (e.g., pivot from LLMs -> Vector Search/RAG -> Multi-Agent Routing -> Async System Scalability).
- Ask ONE clear, practical engineering scenario at a time. Keep questions simple, realistic, and applied — NO academic textbook definitions or rigid trivia questions.
- Adapt based on turn count:
  • Turn 1: Warm welcome + First core question from Topic A.
  • Turn 2-3: Deep dive into applied scenario or edge case on Topic A/B.
  • Turn 4-5: Pivot to Topic C (e.g. System Design, RAG, or Async execution).
  • Turn 6-7: Pivot to Topic D (e.g. Failure recovery, Multi-Agent routing, latency).
  • Turn 8+: Smoothly wrap up and offer a warm synthesis.
- If answer is good: acknowledge in 1 short sentence ("Great point!", "Solid design decision"), then ask the next question on a fresh topic.
- Keep turns concise (2-3 sentences max).
- Maintain a warm, encouraging, sharp tone.
"""

# ─── INTERVIEW ENDPOINTS ──────────────────────────────────────────────────────
@app.post("/api/session/start", tags=["Interview"])
def start_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    
    # Build system context from course
    course_prompt = f"Course/Curriculum Context:\n{req.course_context}"
    
    opening_prompt = f"""You are starting a technical interview with {req.candidate_name}.

{course_prompt}

Begin the interview: warmly introduce yourself as HireGenie AI Interviewer, state the candidate's name, and ask your FIRST practical technical question based on the curriculum topics above."""

    ai_response = LLMService.generate_response(
        prompt=opening_prompt,
        system_instruction=INTERVIEWER_SYSTEM
    )

    history = [
        {"role": "assistant", "content": ai_response}
    ]

    session = InterviewSessionDB(
        session_id=session_id,
        candidate_name=req.candidate_name,
        course_context=req.course_context,
        history=history,
        status="active",
        question_count=1
    )
    db.add(session)
    db.commit()

    return {
        "session_id": session_id,
        "ai_message": ai_response,
        "tag": "Interview Started",
        "question_number": 1
    }

@app.post("/api/session/chat", tags=["Interview"])
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(InterviewSessionDB).filter_by(session_id=req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    # Append user message
    history = list(session.history or [])
    history.append({"role": "user", "content": req.user_message})

    # Build LLM conversation
    course_prompt = f"\nCourse/Curriculum Context:\n{session.course_context}"
    
    progress_note = f"\n\n[INTERNAL: Questions asked so far: {session.question_count}. Try to cover at least 8 questions across different topics before ending.]"

    ai_response = LLMService.generate_response(
        prompt=req.user_message + progress_note,
        conversation_history=history[:-1],  # exclude last user msg (already in prompt)
        system_instruction=INTERVIEWER_SYSTEM + course_prompt
    )

    history.append({"role": "assistant", "content": ai_response})

    # Detect tag
    lower = ai_response.lower()
    tag = "Next Topic"
    if any(w in lower for w in ["follow", "elaborate", "can you explain more", "clarify", "dig deeper"]):
        tag = "Adaptive Follow-up"
    elif any(w in lower for w in ["next", "move on", "great answer", "excellent"]):
        tag = "Topic Transition"

    session.history = history
    session.question_count = session.question_count + 1
    session.updated_at = datetime.datetime.utcnow()
    db.commit()

    return {
        "session_id": req.session_id,
        "ai_message": ai_response,
        "tag": tag,
        "question_number": session.question_count
    }

@app.post("/api/session/end", tags=["Interview"])
def end_session(req: EndSessionRequest, db: Session = Depends(get_db)):
    session = db.query(InterviewSessionDB).filter_by(session_id=req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    history = session.history or []
    transcript = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history])

    eval_prompt = f"""You are the Lead Technical Evaluator. Based on this complete interview transcript, generate a comprehensive candidate assessment.

Candidate Name: {session.candidate_name}
Course Context: {session.course_context[:300]}
Total Questions Asked: {session.question_count}

Interview Transcript:
{transcript}

Return ONLY valid JSON (no markdown, no preamble):
{{
  "overall_summary": "2-3 paragraph comprehensive summary of candidate performance...",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "topic_breakdown": [
    {{"topic": "Topic Name", "assessment": "strong|moderate|weak", "notes": "specific observation"}}
  ],
  "readiness_signal": "Ready|Needs Practice|Not Ready",
  "total_questions": {session.question_count},
  "radar_scores": {{
    "System Architecture": 80,
    "Problem Solving": 85,
    "Tool Mastery": 75,
    "Code Quality": 88,
    "Edge Cases": 70,
    "Communication": 90
  }}
}}"""

    resp = LLMService.generate_response(
        prompt=eval_prompt,
        system_instruction="Output strictly valid JSON only. No markdown fences.",
        response_json=True
    )

    try:
        data = LLMService.parse_json_response(resp)
    except Exception:
        data = {
            "overall_summary": f"{session.candidate_name} completed the technical interview across {session.question_count} questions.",
            "strengths": ["Clear technical communication", "Good understanding of core concepts"],
            "weaknesses": ["Deeper production-level elaboration recommended"],
            "topic_breakdown": [{"topic": "General AI Engineering", "assessment": "moderate", "notes": "Satisfactory overall performance"}],
            "readiness_signal": "Needs Practice",
            "total_questions": session.question_count,
            "radar_scores": {"System Architecture": 75, "Problem Solving": 80, "Tool Mastery": 70, "Code Quality": 75, "Edge Cases": 65, "Communication": 85}
        }

    # Save evaluation to DB
    existing = db.query(EvaluationDB).filter_by(session_id=req.session_id).first()
    if existing:
        db.delete(existing)
    
    eval_obj = EvaluationDB(
        session_id=req.session_id,
        candidate_name=session.candidate_name,
        readiness_signal=data.get("readiness_signal", "Ready"),
        overall_summary=data.get("overall_summary", ""),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        topic_breakdown=data.get("topic_breakdown", []),
        radar_scores=data.get("radar_scores", {}),
        total_questions=data.get("total_questions", session.question_count)
    )
    db.add(eval_obj)
    session.status = "completed"
    db.commit()

    return {
        "session_id": req.session_id,
        "candidate_name": session.candidate_name,
        **data
    }

@app.get("/api/sessions", tags=["Sessions"])
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(InterviewSessionDB).order_by(InterviewSessionDB.created_at.desc()).limit(50).all()
    return [{"session_id": s.session_id, "candidate_name": s.candidate_name, 
             "status": s.status, "question_count": s.question_count,
             "created_at": str(s.created_at)} for s in sessions]

@app.get("/api/sessions/{session_id}", tags=["Sessions"])
def get_session(session_id: str, db: Session = Depends(get_db)):
    s = db.query(InterviewSessionDB).filter_by(session_id=session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    eval_obj = db.query(EvaluationDB).filter_by(session_id=session_id).first()
    return {
        "session_id": s.session_id,
        "candidate_name": s.candidate_name,
        "status": s.status,
        "question_count": s.question_count,
        "history": s.history,
        "created_at": str(s.created_at),
        "evaluation": {
            "readiness_signal": eval_obj.readiness_signal,
            "overall_summary": eval_obj.overall_summary,
            "strengths": eval_obj.strengths,
            "weaknesses": eval_obj.weaknesses,
            "topic_breakdown": eval_obj.topic_breakdown,
            "radar_scores": eval_obj.radar_scores
        } if eval_obj else None
    }

@app.get("/api/curriculum", tags=["Curriculum"])
def list_curriculum(db: Session = Depends(get_db)):
    return db.query(CurriculumDayDB).order_by(CurriculumDayDB.day).all()

@app.get("/api/candidates", tags=["Candidates"])
def list_candidates(db: Session = Depends(get_db)):
    return db.query(CandidateDB).all()

@app.post("/api/candidates", status_code=201, tags=["Candidates"])
def create_candidate(c: CandidateCreate, db: Session = Depends(get_db)):
    existing = db.query(CandidateDB).filter_by(candidate_id=c.candidate_id).first()
    if existing:
        return existing
    obj = CandidateDB(**c.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@app.get("/api/logs", tags=["Logs"])
def ai_usage_logs(db: Session = Depends(get_db)):
    """Returns AI usage logs — session history, evaluation outcomes, and LLM call stats."""
    sessions = db.query(InterviewSessionDB).order_by(InterviewSessionDB.created_at.desc()).limit(100).all()
    evals = db.query(EvaluationDB).all()
    eval_map = {e.session_id: e for e in evals}

    logs = []
    for s in sessions:
        e = eval_map.get(s.session_id)
        logs.append({
            "session_id": s.session_id,
            "candidate_name": s.candidate_name,
            "status": s.status,
            "questions_asked": s.question_count,
            "turns": len(s.history or []),
            "created_at": str(s.created_at),
            "updated_at": str(s.updated_at),
            "readiness_signal": e.readiness_signal if e else None,
            "strengths_count": len(e.strengths or []) if e else 0,
            "topics_evaluated": len(e.topic_breakdown or []) if e else 0,
            "llm_pipeline": "Groq (Llama-3.3-70B) → Gemini-2.0-Flash → Cerebras → OpenRouter"
        })

    total_sessions = db.query(InterviewSessionDB).count()
    completed = db.query(InterviewSessionDB).filter_by(status="completed").count()
    active = db.query(InterviewSessionDB).filter_by(status="active").count()

    return {
        "platform": "HireGenie Pro v2.0",
        "summary": {
            "total_sessions": total_sessions,
            "completed_interviews": completed,
            "active_sessions": active,
            "total_evaluations": len(evals),
        },
        "llm_providers": [
            {"name": "Groq (Llama-3.3-70B)", "priority": 1, "role": "Primary — fast interview Q&A"},
            {"name": "Google Gemini 2.0 Flash", "priority": 2, "role": "Fallback — complex reasoning"},
            {"name": "Cerebras (Llama-3.3-70B)", "priority": 3, "role": "Ultra-fast fallback"},
            {"name": "OpenRouter", "priority": 4, "role": "Final fallback"},
        ],
        "ai_usage_logs": logs
    }

@app.delete("/api/candidates/{cid}", tags=["Candidates"])
def delete_candidate(cid: str, db: Session = Depends(get_db)):
    obj = db.query(CandidateDB).filter_by(candidate_id=cid).first()
    if not obj:
        raise HTTPException(404, "Not found")
    db.delete(obj)
    db.commit()
    return {"deleted": cid}
