"""Screen 07 seed: classroom stage, live poll with votes and moderated Q&A for
Thursday's RAG session (PDF 13). The meeting is not started; the trainer
starts it from the room."""
import uuid

from sqlalchemy import delete, select

from models.schema import JoinEvent, LiveMeeting, LivePoll, LivePollVote, QaQuestion, QaUpvote, SessionAttendance, Student, User

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


DEMO_STAGE = dict(provider="fake", external_meeting_id=f"irep-{SESSION}", is_recording=True, sharing_user_name="Arun K",
                  shared_file="rag_demo.ipynb", shared_source="Shared via Virtual Labs", shared_code=SHARED_CODE,
                  flow_title="RAG flow", flow_steps=FLOW, started_at=None, ended_at=None, finalized=False,
                  join_url=None, share_grants=[])


def seed_screen07(db, college_id: str = "col_demo_001") -> int:
    from core.config import settings
    existing = db.execute(select(LiveMeeting).filter_by(session_id=SESSION)).scalars().first()
    if existing is not None and existing.provider == "fake" and existing.shared_file == "rag_demo.ipynb":
        # the demo room is intact unless a class run (a demo or the e2e) started it, voted or asked questions:
        # then it is rebuilt below so the trainer finds the waiting room and the seeded poll again (rule 12)
        polls = list(db.execute(select(LivePoll.id).where(LivePoll.session_id == SESSION)).scalars())
        votes = db.execute(select(LivePollVote.id).where(LivePollVote.poll_id == "poll_rag_notes")).all()
        questions = db.execute(select(QaQuestion.id).where(QaQuestion.session_id == SESSION)).all()
        used = (existing.started_at or existing.ended_at or existing.finalized or existing.share_grants
                or polls != ["poll_rag_notes"] or len(votes) != 30 or len(questions) != 3)
        if not used:
            return 0
    elif existing is not None and (settings.LIVE_CLASS_ADAPTER or "fake").lower() != "fake":
        return 0          # a developer is trying LiveKit / Teams on this room: leave their meeting alone
    # the session is upcoming, so its join events and auto attendance only ever come from a class run
    db.execute(delete(JoinEvent).where(JoinEvent.session_id == SESSION))
    db.execute(delete(SessionAttendance).where(SessionAttendance.session_id == SESSION))
    # the meeting is gone, or was replaced while trying LiveKit (provider livekit, no stage): a re-seed restores
    # the demo room (rule 12), polls and Q&A included
    qids = list(db.execute(select(QaQuestion.id).where(QaQuestion.session_id == SESSION)).scalars())
    pids = list(db.execute(select(LivePoll.id).where(LivePoll.session_id == SESSION)).scalars())
    db.execute(delete(QaUpvote).where(QaUpvote.question_id.in_(qids or ["_"])))
    db.execute(delete(QaQuestion).where(QaQuestion.session_id == SESSION))
    db.execute(delete(LivePollVote).where(LivePollVote.poll_id.in_(pids or ["_"])))
    db.execute(delete(LivePoll).where(LivePoll.session_id == SESSION))
    db.flush()
    if existing is not None:
        for k, v in DEMO_STAGE.items():
            setattr(existing, k, v)
    else:
        db.add(LiveMeeting(id=f"lm_{SESSION}", college_id=college_id, session_id=SESSION, **DEMO_STAGE))
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
