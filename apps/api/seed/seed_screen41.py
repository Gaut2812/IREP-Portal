"""Screens 41 and 40 seed (S14): one published demo survey for parents, and hygiene. Re-seeding
removes college announcements (with their notifications and group posts) and any other survey
or response created by tests or demos. Stray college threads go with the screen 35 seed."""
import datetime

from sqlalchemy import delete, select

from models.schema import Broadcast, GroupMessage, Notification, OutboxEvent, Survey, SurveyResponse

DEMO_SURVEY = "sv_demo_term_feedback"
QUESTIONS = [
    {"id": "q1", "kind": "rating", "text_en": "How happy are you with your child's progress this term?",
     "text_ta": "இந்தப் பருவத்தில் உங்கள் பிள்ளையின் முன்னேற்றத்தில் எவ்வளவு திருப்தி?", "required": True},
    {"id": "q2", "kind": "choice", "text_en": "How often do you hear from the trainer?", "text_ta": "பயிற்சியாளரிடமிருந்து எவ்வளவு அடிக்கடி தகவல் வருகிறது?",
     "options_en": ["Every week", "Every month", "Rarely"], "options_ta": ["ஒவ்வொரு வாரமும்", "ஒவ்வொரு மாதமும்", "அரிதாக"], "required": True},
    {"id": "q3", "kind": "text", "text_en": "Anything we should do better?", "text_ta": "நாங்கள் எதை மேம்படுத்தலாம்?", "required": False},
]


def seed_screen41(db, college_id: str = "col_demo_001") -> None:
    college = list(db.execute(select(Broadcast.id).where(Broadcast.college_id == college_id, Broadcast.author_role == "college")).scalars())
    for bid in college:
        db.execute(delete(Notification).where(Notification.link.like(f"%announcement={bid}")))
    db.execute(delete(OutboxEvent).where(OutboxEvent.event_type == "broadcast.chunk", OutboxEvent.entity_id.in_(college or ["_"])))
    db.execute(delete(Broadcast).where(Broadcast.id.in_(college or ["_"])))
    db.execute(delete(GroupMessage).where(GroupMessage.college_id == college_id, GroupMessage.id.like("gm_bc_%")))

    stray = list(db.execute(select(Survey.id).where(Survey.college_id == college_id, Survey.id != DEMO_SURVEY)).scalars())
    db.execute(delete(SurveyResponse).where(SurveyResponse.survey_id.in_(stray + [DEMO_SURVEY])))
    db.execute(delete(Survey).where(Survey.id.in_(stray or ["_"])))
    db.execute(delete(Notification).where(Notification.college_id == college_id, Notification.kind == "survey"))
    s = db.get(Survey, DEMO_SURVEY)
    if s is None:
        s = Survey(id=DEMO_SURVEY, college_id=college_id)
        db.add(s)
    s.title_en, s.title_ta, s.questions, s.status = "Term feedback", "பருவக் கருத்துக் கணிப்பு", QUESTIONS, "published"
    s.published_at = datetime.datetime.utcnow() - datetime.timedelta(days=3)
    s.closes_on = datetime.date.today() + datetime.timedelta(days=14)
    db.flush()
