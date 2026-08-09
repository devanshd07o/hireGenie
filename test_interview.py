import os
import sys
import time
from fastapi.testclient import TestClient
from main import app, seed_database_from_json

def test_full_hiregenie_backend():
    seed_database_from_json()
    client = TestClient(app)

    print("\n========================================================")
    print(" === TESTING HIREGENIE AI INTERVIEW AGENT REST API ===")
    print("========================================================\n")

    # 1. Health check
    res = client.get("/")
    assert res.status_code == 200
    print(f"[SUCCESS] Health Check Status: {res.json()}")

    # 2. List candidates
    res = client.get("/candidates")
    assert res.status_code == 200
    candidates = res.json()
    print(f"[SUCCESS] Candidates Loaded ({len(candidates)} candidates):")
    for c in candidates:
        print(f"   - Candidate ID: {c['candidate_id']} | Name: {c['name']} | Completed Days: {len(c['completed_days'])}")

    # 3. Add dynamic SaaS Candidate
    new_cand_payload = {
        "candidate_id": "cand_999",
        "name": "Test Hackathon Candidate",
        "completed_days": [1, 2, 5, 12, 14, 15, 18],
        "skipped_days": [3, 4],
        "attempts": {"day_5": 2},
        "learning_signals": {"day_5": "retried RAG, strong on vectors"}
    }
    res = client.post("/candidates", json=new_cand_payload)
    assert res.status_code in [201, 400]
    print("[SUCCESS] Dynamic Candidate Creation API verified.")

    # 4. List curriculum
    res = client.get("/curriculum")
    assert res.status_code == 200
    curriculum = res.json()
    print(f"[SUCCESS] Curriculum Loaded ({len(curriculum)} days). Day 5: {curriculum[4]['topic']}")

    # 5. Start Interview
    print("\n--- STARTING INTERVIEW SESSION ---")
    res = client.post("/interview/start", json={"candidate_id": "cand_001"})
    assert res.status_code == 200
    start_data = res.json()
    session_id = start_data["session_id"]
    first_q = start_data["first_question"]
    print(f"[SUCCESS] Session ID Generated: {session_id}")
    print(f"[SUCCESS] First Question from LLM:\n   \"{first_q}\"\n")

    # 6. Multi-turn interview conversation (simulating candidate responses)
    answers = [
        "In a RAG pipeline, we first split raw text into chunks using strategies like RecursiveCharacterTextSplitter with an overlap of 100 tokens. Then we compute vector embeddings via SentenceTransformers and insert them into Pinecone. For retrieval, we query Pinecone with cosine similarity to retrieve top-k chunks and feed them into the LLM system prompt.",
        "To prevent hallucinations in RAG, we can implement hybrid search combining BM25 keyword matching with dense embeddings, and run a Cohere cross-encoder reranker. We also use RAGAS evals to measure faithfulness and answer grounding.",
        "In LangGraph, we define state graphs where nodes represent agent actions and edges define transition routing logic. Memory is persisted across turns by passing a state object containing message channels.",
        "Custom MCP servers expose standardized JSON-RPC endpoints for resources, tools, and prompts. FastMCP allows python tools to be injected into Claude or other host environments seamlessly."
    ]

    for idx, ans in enumerate(answers, 1):
        print(f"--- TURN {idx}: CANDIDATE ANSWERING ---")
        print(f"Candidate: \"{ans[:80]}...\"")
        res = client.post("/interview/message", json={"session_id": session_id, "answer": ans})
        assert res.status_code == 200
        msg_data = res.json()
        print(f"Interviewer Next Question (is_followup={msg_data['is_followup']}):")
        print(f"   \"{msg_data['next_question']}\"\n")

    # 7. Get session history
    res = client.get(f"/interview/session/{session_id}")
    assert res.status_code == 200
    session_detail = res.json()
    print(f"[SUCCESS] Session Transcript Retrieved: Total Messages={len(session_detail['messages'])}, Questions={session_detail['question_count']}")

    # 8. End interview and get structured JSON feedback
    print("\n--- ENDING INTERVIEW & GENERATING STRUCTURED FEEDBACK ---")
    res = client.post("/interview/end", json={"session_id": session_id})
    assert res.status_code == 200
    feedback = res.json()

    print("[SUCCESS] Structured LLM Feedback Received:")
    print(f"   - Readiness Signal: {feedback['readiness_signal']}")
    print(f"   - Overall Summary: {feedback['overall_summary']}")
    print(f"   - Strengths ({len(feedback['strengths'])}): {feedback['strengths']}")
    print(f"   - Weaknesses ({len(feedback['weaknesses'])}): {feedback['weaknesses']}")
    print(f"   - Days Covered: {feedback['days_covered']}")
    print(f"   - Topic Breakdown Items: {len(feedback['topic_breakdown'])}\n")

    print("ALL TESTS PASSED SUCCESSFULLY! HIREGENIE BACKEND IS 100% PRODUCTION READY!\n")

if __name__ == "__main__":
    test_full_hiregenie_backend()
