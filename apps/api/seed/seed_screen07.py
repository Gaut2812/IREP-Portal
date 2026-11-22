"""Screen 07 seed: classroom stage, live poll with votes and moderated Q&A for
Thursday's RAG session (PDF 13). The meeting is not started; the trainer
starts it from the room."""
import uuid

from sqlalchemy import select

from models.schema import LiveMeeting, LivePoll, LivePollVote, QaQuestion, QaUpvote, Student, User

SESSION = "sess_thu_rag"
SHARED_CODE = """# Step 3: retrieve relevant notes, then ask the LLM
chunks = vector_db.search(question, top_k=3)
context = "\n".join(c.text for c in chunks)

prompt = f"Answer using only this context:\n{context}\n\nQ: {question}"
answer = llm.generate(prompt)

# Discuss: what happens if the answer is not in the notes?"""
FLOW = [
    {"step": 1, "title": "Question", "color": "blue"},
    {"step": 2, "title": "Search vector DB", "color": "green"},
    {"step": 3, "title": "Add context to prompt", "color": "amber"},
    {"step": 4, "title": "LLM answers", "color": "purple"},
]


def seed_screen07(db, college_id: str = "col_demo_001") -> int:
    if db.execute(select(LiveMeeting).filter_by(session_id=SESSION)).first():
        return 0
    db.add(LiveMeeting(id=f"lm_{SESSION}", college_id=college_id, session_id=SESSION, provider="fake",
                       external_meeting_id=f"irep-{SESSION}", is_recording=True, sharing_user_name="Arun K",
                       shared_file="rag_demo.ipynb", shared_source="Shared via Virtual Labs", shared_code=SHARED_CODE,
                       flow_title="RAG flow", flow_steps=FLOW))
    poll = LivePoll(id="poll_rag_notes", college_id=college_id, session_id=SESSION,
                    question="If the answer is not in the notes, the model should...",
                    options=[{"key": "a", "text": "Make up an answer", "color": "red"},
                             {"key": "b", "text": "Say it doesn't know", "color": "teal"},
                             {"key": "c", "text": "Search the web", "color": "blue"}],
                    is_open=True, created_by="usr_arun_01")
    db.add(poll)
    db.flush()
    classmates = db.execute(
        select(Student.user_id).where(Student.batch_id == "bat_aids_s5_aids", Student.id != "std_priya_01").order_by(Student.id)
    ).scalars().all()
    # 30 votes: 2 / 26 / 2  -> Priya's vote makes 31 (PDF: 6% / 87% / 7%)
    plan = ["a"] * 2 + ["b"] * 26 + ["c"] * 2
    for uid, key in zip(classmates, plan):
        db.add(LivePollVote(id=f"pv_{uuid.uuid4().hex[:16]}", college_id=college_id, poll_id=poll.id, user_id=uid, option_key=key))
    names = {u.name: u.id for u in db.execute(select(User).where(User.name.in_(["Vikram R", "Sneha N", "Ananya P"]))).scalars().all()}
    questions = [
        ("qa_topk", "Vikram R", "How do we choose top_k?", 9, 31 * 60 + 40),
        ("qa_college_notes", "Sneha N", "Can we use our own college notes for the RAG mini-lab?", 5, None),
        ("qa_chunk_size", "Ananya P", "Is chunk size related to accuracy?", 2, None),
    ]
    for qid, author, text, votes, answered in questions:
        db.add(QaQuestion(id=qid, college_id=college_id, session_id=SESSION, author_user_id=names.get(author),
                          author_name=author, text=text, answered_at_sec=answered))
        db.flush()
        for uid in classmates[10:10 + votes]:
            db.add(QaUpvote(id=f"qu_{uuid.uuid4().hex[:16]}", college_id=college_id, question_id=qid, user_id=uid))
    db.flush()
    return 1
