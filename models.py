import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, Boolean, Text, JSON, DateTime, ForeignKey
from database import Base


# ==========================================
# SQLALCHEMY ORM MODELS
# ==========================================

class CandidateDB(Base):
    __tablename__ = "candidates"

    candidate_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    completed_days = Column(JSON, default=list)
    skipped_days = Column(JSON, default=list)
    attempts = Column(JSON, default=dict)
    learning_signals = Column(JSON, default=dict)


class CurriculumDayDB(Base):
    __tablename__ = "curriculum_days"

    day = Column(Integer, primary_key=True, index=True)
    module = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    learning_objectives = Column(JSON, default=list)
    tools_used = Column(JSON, default=list)
    difficulty = Column(String, default="intermediate")


class InterviewSessionDB(Base):
    __tablename__ = "interview_sessions"

    session_id = Column(String, primary_key=True, index=True)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id"), nullable=False)
    status = Column(String, default="in_progress")  # "in_progress", "completed"
    question_count = Column(Integer, default=0)
    target_days = Column(JSON, default=list)  # Days selected for this interview
    covered_days = Column(JSON, default=list)  # Days covered so far
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SessionMessageDB(Base):
    __tablename__ = "session_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("interview_sessions.session_id"), nullable=False, index=True)
    sender = Column(String, nullable=False)  # "interviewer" or "candidate"
    content = Column(Text, nullable=False)
    day_covered = Column(Integer, nullable=True)
    is_followup = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class SessionFeedbackDB(Base):
    __tablename__ = "session_feedbacks"

    session_id = Column(String, primary_key=True, index=True)
    overall_summary = Column(Text, nullable=False)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    topic_breakdown = Column(JSON, default=list)
    readiness_signal = Column(String, nullable=False)  # "Ready", "Needs Practice", "Not Ready"
    total_questions_asked = Column(Integer, nullable=False)
    days_covered = Column(JSON, default=list)


# ==========================================
# PYDANTIC SCHEMAS (API Request / Response)
# ==========================================

# Candidates
class CandidateCreate(BaseModel):
    candidate_id: str = Field(..., example="cand_005")
    name: str = Field(..., example="Rahul Mehta")
    completed_days: List[int] = Field(default_factory=list, example=[1, 2, 3, 5, 10])
    skipped_days: List[int] = Field(default_factory=list, example=[4, 6])
    attempts: Dict[str, int] = Field(default_factory=dict, example={"day_5": 2})
    learning_signals: Dict[str, str] = Field(default_factory=dict, example={"day_5": "struggled with RAG"})


class CandidateResponse(CandidateCreate):
    class Config:
        from_attributes = True


# Curriculum
class CurriculumDayCreate(BaseModel):
    day: int = Field(..., example=5)
    module: str = Field(..., example="Retrieval-Augmented Generation")
    topic: str = Field(..., example="Building a RAG Pipeline with Vector Stores")
    learning_objectives: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    difficulty: str = Field("intermediate", example="intermediate")


class CurriculumDayResponse(CurriculumDayCreate):
    class Config:
        from_attributes = True


# Interview Endpoints
class StartInterviewRequest(BaseModel):
    candidate_id: str = Field(..., example="cand_001")


class StartInterviewResponse(BaseModel):
    session_id: str
    first_question: str
    metadata: Dict[str, Any]


class MessageInterviewRequest(BaseModel):
    session_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    answer: str = Field(..., example="In a RAG pipeline, chunking breaks documents into smaller segments using strategies like RecursiveCharacterTextSplitter. Embeddings are generated using models like SentenceTransformers and stored in vector DBs like Pinecone for cosine similarity search.")


class ProgressMetadata(BaseModel):
    current_question_number: int
    estimated_total_questions: int = 10
    days_covered: List[int]
    status: str


class MessageInterviewResponse(BaseModel):
    session_id: str
    next_question: str
    is_followup: bool
    progress: ProgressMetadata


class EndInterviewRequest(BaseModel):
    session_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")


class TopicAssessment(BaseModel):
    day: int
    topic: str
    assessment: str  # "strong", "moderate", "weak", "unclear"
    notes: str


class EndInterviewResponse(BaseModel):
    session_id: str
    overall_summary: str
    strengths: List[str]
    weaknesses: List[str]
    topic_breakdown: List[TopicAssessment]
    readiness_signal: str  # "Ready" | "Needs Practice" | "Not Ready"
    total_questions_asked: int
    days_covered: List[int]


class SessionMessageSchema(BaseModel):
    sender: str
    content: str
    day_covered: Optional[int] = None
    is_followup: bool = False
    timestamp: datetime.datetime

    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    session_id: str
    candidate_id: str
    status: str
    question_count: int
    target_days: List[int]
    covered_days: List[int]
    created_at: datetime.datetime
    messages: List[SessionMessageSchema]
    feedback: Optional[EndInterviewResponse] = None
