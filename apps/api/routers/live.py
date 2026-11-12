from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/live", tags=["Live Classroom"])

class PollVoteRequest(BaseModel):
    option: str # a, b, c

# --- SCREEN 07: Live Classroom (PDF 13) ---
@router.get("/{session_id}")
def get_live_classroom_state(session_id: str):
    return {
        "session_id": session_id,
        "title": "Future Skills: LLM APIs & RAG",
        "subtext": "AI & DS · Sem 5 · Week 8 · Thu",
        "is_recording": True,
        "timer": "00:38:12 / 01:00:00",
        "attendance_status": "Attendance on track",
        "sharing_info": {
            "trainer": "Arun K is sharing screen",
            "file": "rag_demo.ipynb",
            "source": "Shared via Virtual Labs"
        },
        "shared_code": """# RAG Pipeline Demonstration with Vector Search
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 1. Retrieve most relevant context chunks
query = "What is the penalty for late sprint submissions?"
docs = vectorstore.similarity_search(query, k=3)

# 2. Augment prompt with context
augmented_prompt = f\"\"\"Context:
{docs[0].page_content}

Question: {query}
Answer:\"\"\"

# 3. Stream response from model
response = llm.invoke(augmented_prompt)
print(response)""",
        "rag_flow_steps": [
            {"step": 1, "title": "Question", "color": "blue"},
            {"step": 2, "title": "Search vector DB", "color": "green"},
            {"step": 3, "title": "Add context to prompt", "color": "amber"},
            {"step": 4, "title": "LLM answers", "color": "purple"}
        ],
        "participants": [
            {"name": "Arun K", "role": "Trainer", "initials": "AK", "color": "blue"},
            {"name": "Priya R", "role": "You", "initials": "PR", "color": "teal"},
            {"name": "Sneha N", "role": "Student", "initials": "SN", "color": "purple"},
            {"name": "Vikram R", "role": "Student", "initials": "VR", "color": "amber"},
            {"name": "Ananya P", "role": "Student", "initials": "AP", "color": "pink"}
        ],
        "more_participants_count": 36,
        "live_poll": {
            "question": "If the answer is not in the notes, the model should...",
            "total_votes": 31,
            "options": [
                {"text": "Make up an answer", "pct": 6, "color": "red"},
                {"text": "Say it doesn't know", "pct": 87, "color": "teal"},
                {"text": "Search the web", "pct": 7, "color": "blue"}
            ]
        },
        "moderated_qa": [
            {
                "id": "qa_1",
                "question": "How do we choose top_k for similarity search?",
                "author": "Sneha N",
                "upvotes": 14,
                "answered_at": "Answered live at 31:40"
            },
            {
                "id": "qa_2",
                "question": "Does chunk size affect embedding quality directly?",
                "author": "Karthik S",
                "upvotes": 9,
                "answered_at": None
            }
        ],
        "auto_attendance": {
            "joined_time": "10:58 AM",
            "present_minutes": 38,
            "total_minutes": 60,
            "threshold_minutes": 45,
            "threshold_pct": 75,
            "note": "Marked present automatically at 45 min (75% of the session)."
        }
    }

@router.post("/{session_id}/poll/vote")
def vote_live_poll(session_id: str, req: PollVoteRequest):
    return {"success": True, "message": "Vote recorded."}
