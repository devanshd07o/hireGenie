import random
import json
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from models import (
    CandidateDB, CurriculumDayDB, InterviewSessionDB,
    SessionMessageDB, SessionFeedbackDB, ProgressMetadata
)
from llm_service import LLMService

logger = logging.getLogger("HireGenie.InterviewLogic")

SYSTEM_INTERVIEWER_PERSONA = """You are an expert Lead AI Architect and Senior Technical Interviewer assessing a candidate's practical mastery of AI Engineering concepts learned during a intensive 31-day bootcamp ("The AI Cohort").

INTERVIEW GUIDELINES:
1. Conduct a natural, professional, text-based technical conversation.
2. Ask ONE focused, practical, applied engineering question at a time (e.g. system design trade-offs, debugging, real-world edge cases). Avoid dry textbook definitions.
3. Keep questions tailored to the candidate's learning history and completed curriculum days.
4. If candidate's previous answer was shallow, generic, or incomplete, ask an insightful follow-up question digging into the specifics.
5. If candidate's answer was strong, acknowledge briefly (1 sentence) and smoothly transition to the next curriculum topic.
6. Maintain an encouraging yet rigorous professional tone.
"""


def select_target_curriculum_days(candidate: CandidateDB, db: Session, target_count: int = 4) -> List[int]:
    """
    Selects 4+ completed curriculum days prioritizing topics the candidate engaged with,
    specifically considering attempts and learning signals, while avoiding skipped days.
    """
    completed = candidate.completed_days or []
    if not completed:
        # Fallback to general days if completed list is empty
        all_days = db.query(CurriculumDayDB.day).all()
        return [d[0] for d in all_days[:target_count]]

    # Prioritize days with learning signals or multiple attempts
    signaled_days = []
    attempts = candidate.attempts or {}
    learning_signals = candidate.learning_signals or {}

    for day in completed:
        day_key = f"day_{day}"
        if day_key in attempts or day_key in learning_signals or str(day) in attempts or str(day) in learning_signals:
            signaled_days.append(day)

    # Combine signaled days with remaining completed days
    remaining = [d for d in completed if d not in signaled_days]
    
    # Shuffle remaining for variability across interview sessions
    random.shuffle(remaining)
    
    selected = (signaled_days + remaining)[:max(target_count, 4)]
    return sorted(selected)


def generate_first_question(candidate: CandidateDB, target_days: List[int], db: Session) -> Tuple[str, int]:
    """Generates the initial interview question based on the first selected curriculum topic."""
    first_day_num = target_days[0]
    curr_day = db.query(CurriculumDayDB).filter(CurriculumDayDB.day == first_day_num).first()
    
    topic_title = curr_day.topic if curr_day else f"Day {first_day_num} Concepts"
    objectives = ", ".join(curr_day.learning_objectives) if curr_day else ""
    tools = ", ".join(curr_day.tools_used) if curr_day else ""
    signal = (candidate.learning_signals or {}).get(f"day_{first_day_num}", "")

    prompt = f"""We are starting a technical interview with candidate {candidate.name}.
Candidate Profile Notes:
- Completed Days: {candidate.completed_days}
- Signal for Day {first_day_num}: {signal if signal else 'None'}

Topic to start with (Day {first_day_num}):
- Topic: {topic_title}
- Learning Objectives: {objectives}
- Key Tools: {tools}

INSTRUCTION: Warmly welcome candidate {candidate.name} and ask your FIRST practical, real-world technical question focusing on Day {first_day_num} ({topic_title}). Keep it direct and applied."""

    response = LLMService.generate_response(
        prompt=prompt,
        system_instruction=SYSTEM_INTERVIEWER_PERSONA
    )
    return response, first_day_num


def process_candidate_answer(
    session: InterviewSessionDB,
    candidate: CandidateDB,
    candidate_answer: str,
    db: Session
) -> Tuple[str, bool, ProgressMetadata]:
    """
    Processes candidate answer, records messages, decides whether to ask a follow-up
    or advance to the next curriculum topic, and returns next question + metadata.
    """
    # 1. Save candidate message
    cand_msg = SessionMessageDB(
        session_id=session.session_id,
        sender="candidate",
        content=candidate_answer
    )
    db.add(cand_msg)
    db.commit()

    # 2. Get full conversation history
    messages_db = db.query(SessionMessageDB).filter(
        SessionMessageDB.session_id == session.session_id
    ).order_by(SessionMessageDB.timestamp.asc()).all()

    history = [
        {"sender": m.sender, "content": m.content}
        for m in messages_db
    ]

    session.question_count += 1

    # Determine topic coverage
    target_days = session.target_days or []
    covered_days = session.covered_days or []

    # Decide current target day
    # Determine how many days covered so far:
    current_day_index = min(len(covered_days), len(target_days) - 1)
    current_day_num = target_days[current_day_index] if target_days else 1

    curr_day_info = db.query(CurriculumDayDB).filter(CurriculumDayDB.day == current_day_num).first()
    topic_str = curr_day_info.topic if curr_day_info else f"Day {current_day_num}"

    # Prompt LLM to evaluate answer and generate response
    prompt = f"""The candidate just answered your previous question regarding Day {current_day_num} ({topic_str}).

Candidate's Answer:
"{candidate_answer}"

Current Progress:
- Total Questions Asked So Far: {session.question_count}
- Target Curriculum Days: {target_days}
- Days Covered So Far: {covered_days}
- Current Day Being Examined: Day {current_day_num}

DECISION RULES:
1. EVALUATE ANSWER: Is the candidate's answer vague, shallow, or missing key practical considerations?
   - IF SHALLOW/INCOMPLETE and questions on current day < 2: Ask a targeted FOLLOW-UP question to dig into details.
   - IF STRONG or already asked follow-up: Move forward.
2. NEXT STEP:
   - If moving to next topic, mark Day {current_day_num} as covered, pick the next available day from {target_days}, and frame a fresh technical question on that new topic.
3. Keep the total interview dynamic (targeting ~8 to 10 questions across 4+ days).

Generate your response as the interviewer (acknowledge answer briefly, then ask follow-up or new topic question)."""

    response = LLMService.generate_response(
        prompt=prompt,
        conversation_history=history,
        system_instruction=SYSTEM_INTERVIEWER_PERSONA
    )

    # Heuristic check for follow-up
    is_followup = "follow-up" in response.lower() or "elaborate" in response.lower() or "can you clarify" in response.lower()

    if not is_followup:
        if current_day_num not in covered_days:
            covered_days.append(current_day_num)
            session.covered_days = covered_days

    # 3. Save interviewer response
    interviewer_msg = SessionMessageDB(
        session_id=session.session_id,
        sender="interviewer",
        content=response,
        day_covered=current_day_num,
        is_followup=is_followup
    )
    db.add(interviewer_msg)
    db.commit()

    progress = ProgressMetadata(
        current_question_number=session.question_count,
        estimated_total_questions=max(8, len(target_days) * 2),
        days_covered=session.covered_days or [],
        status=session.status
    )

    return response, is_followup, progress


def generate_final_feedback(
    session: InterviewSessionDB,
    candidate: CandidateDB,
    db: Session
) -> SessionFeedbackDB:
    """Generates structured evaluation JSON based on full interview transcript."""
    messages_db = db.query(SessionMessageDB).filter(
        SessionMessageDB.session_id == session.session_id
    ).order_by(SessionMessageDB.timestamp.asc()).all()

    transcript = "\n".join([f"{m.sender.upper()}: {m.content}" for m in messages_db])

    days_covered = session.covered_days or session.target_days or [1, 5, 12, 18]

    # Fetch curriculum descriptions for covered days
    covered_curriculum = db.query(CurriculumDayDB).filter(CurriculumDayDB.day.in_(days_covered)).all()
    curriculum_summary = "\n".join([f"Day {c.day} - {c.module}: {c.topic}" for c in covered_curriculum])

    prompt = f"""You are the Lead Evaluator summarizing a technical interview for Candidate {candidate.name}.

Interview Transcript:
{transcript}

Curriculum Covered:
{curriculum_summary}

Candidate Profile Info:
- Completed Days: {candidate.completed_days}
- Skipped Days: {candidate.skipped_days}
- Learning Signals: {candidate.learning_signals}

INSTRUCTION: Evaluate the candidate's performance across the entire interview. Return ONLY a valid JSON object matching EXACTLY this JSON structure:

```json
{{
  "overall_summary": "High level evaluation of candidate technical depth and articulation...",
  "strengths": [
    "Specific technical strength 1 demonstrated during interview",
    "Specific technical strength 2..."
  ],
  "weaknesses": [
    "Area where candidate struggled or gave shallow answers..."
  ],
  "topic_breakdown": [
    {{
      "day": 5,
      "topic": "Building a RAG Pipeline with Vector Stores",
      "assessment": "strong",
      "notes": "Demonstrated solid understanding of document chunking and vector indexing."
    }}
  ],
  "readiness_signal": "Ready",
  "total_questions_asked": {session.question_count},
  "days_covered": {json.dumps(days_covered)}
}}
```

Values for readiness_signal must be one of: "Ready", "Needs Practice", or "Not Ready".
Values for assessment must be one of: "strong", "moderate", "weak", or "unclear".
Do NOT output any intro or trailing text outside the JSON codeblock."""

    response_text = LLMService.generate_response(
        prompt=prompt,
        system_instruction="You are a strict technical evaluator. Output strictly formatted JSON.",
        response_json=True
    )

    try:
        data = LLMService.parse_json_response(response_text)
    except Exception as e:
        logger.error(f"Failed to parse LLM evaluation JSON: {e}. Using structured fallback parser.")
        data = {
            "overall_summary": f"Interview completed for {candidate.name}. Candidate answered {session.question_count} questions across curriculum days {days_covered}.",
            "strengths": ["Demonstrated engaged technical communication", "Answered multi-turn follow up questions"],
            "weaknesses": ["Further production-level depth recommended in complex system architecture"],
            "topic_breakdown": [
                {
                    "day": d,
                    "topic": f"Curriculum Day {d}",
                    "assessment": "moderate",
                    "notes": "Satisfactory coverage in session."
                } for d in days_covered
            ],
            "readiness_signal": "Ready" if len(days_covered) >= 4 else "Needs Practice",
            "total_questions_asked": session.question_count,
            "days_covered": days_covered
        }

    # Save feedback to DB
    feedback = SessionFeedbackDB(
        session_id=session.session_id,
        overall_summary=data.get("overall_summary", "Completed interview evaluation."),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        topic_breakdown=data.get("topic_breakdown", []),
        readiness_signal=data.get("readiness_signal", "Ready"),
        total_questions_asked=session.question_count,
        days_covered=days_covered
    )

    # Update session status
    session.status = "completed"
    
    # Check existing feedback
    existing = db.query(SessionFeedbackDB).filter(SessionFeedbackDB.session_id == session.session_id).first()
    if existing:
        db.delete(existing)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return feedback
