"""Screens 46 and 11 seed: one published demo course for semester 5 (all
tracks), so My courses is not empty. Re-seeding restores demo state:
courses, lessons and progress created by tests or demos are removed, demo
progress is cleared (and with it the skill-bar lift it gave Priya, link L33),
and test notification templates are dropped."""
import datetime

from sqlalchemy import delete, select

from core.security import PLATFORM_TENANT
from models.schema import Course, Lesson, LessonProgress, Notification, NotificationTemplate, SkillScore
from seed.seed_screen12 import PRIYA_SKILLS

COURSE_ID = "crs_seed_genai_01"
LESSONS = [
    ("lsn_seed_genai_01", "What a language model does", "மொழி மாதிரி என்ன செய்கிறது",
     "A language model predicts the next token from the text before it. Prompts steer that prediction.",
     "மொழி மாதிரி முந்தைய உரையிலிருந்து அடுத்த சொல்லைக் கணிக்கிறது. அறிவுறுத்தல்கள் அந்தக் கணிப்பை வழிநடத்துகின்றன.", 15),
    ("lsn_seed_genai_02", "Retrieval-augmented generation", "மீட்டெடுப்புடன் கூடிய உருவாக்கம் (RAG)",
     "RAG fetches relevant passages first, then asks the model to answer from them. This keeps answers grounded.",
     "RAG முதலில் தொடர்புடைய பகுதிகளைத் தேடி எடுக்கிறது, பின்னர் அவற்றிலிருந்து பதிலளிக்க மாதிரியைக் கேட்கிறது.", 20),
    ("lsn_seed_genai_03", "Evaluating answers", "பதில்களை மதிப்பிடுதல்",
     "Check answers against a small test set: correctness, citations and refusals when the source is silent.",
     "ஒரு சிறிய சோதனைத் தொகுப்புடன் பதில்களைச் சரிபார்க்கவும்: சரியான தன்மை, மேற்கோள்கள், மூலத்தில் இல்லாதபோது மறுப்பு.", 20),
]


def seed_screen46(db, college_id: str = "col_demo_001") -> None:
    stray = list(db.execute(select(Course.id).where(Course.id != COURSE_ID)).scalars())
    stray_lessons = list(db.execute(select(Lesson.id).where(Lesson.course_id.in_(stray or ["_"]))).scalars())
    db.execute(delete(LessonProgress).where(LessonProgress.lesson_id.in_(stray_lessons or ["_"])))
    db.execute(delete(LessonProgress).where(LessonProgress.college_id == college_id))
    db.execute(delete(Lesson).where(Lesson.course_id.in_(stray or ["_"])))
    db.execute(delete(Lesson).where(Lesson.course_id == COURSE_ID, Lesson.id.not_in([l[0] for l in LESSONS])))
    db.execute(delete(Course).where(Course.id.in_(stray or ["_"])))
    db.execute(delete(Notification).where(Notification.college_id == college_id, Notification.link.like("/student/courses/%")))
    db.execute(delete(NotificationTemplate).where(NotificationTemplate.key.like("test.%")))
    db.execute(delete(NotificationTemplate).where(NotificationTemplate.key.like("e2e.%")))
    for score in db.execute(select(SkillScore).where(SkillScore.student_id == "std_priya_01")).scalars():
        if score.skill_key in PRIYA_SKILLS:
            score.percentage = PRIYA_SKILLS[score.skill_key]

    course = db.get(Course, COURSE_ID)
    if not course:
        course = Course(id=COURSE_ID, college_id=PLATFORM_TENANT)
        db.add(course)
    course.title_en, course.title_ta = "Generative AI foundations", "உருவாக்க AI அடிப்படைகள்"
    course.track, course.semester, course.skill_key, course.status = "All", 5, "future_skills", "published"
    course.published_at = datetime.datetime.utcnow().replace(microsecond=0) - datetime.timedelta(days=7)
    for i, (lid, ten, tta, ben, bta, mins) in enumerate(LESSONS, start=1):
        row = db.get(Lesson, lid)
        if not row:
            row = Lesson(id=lid, college_id=PLATFORM_TENANT, course_id=COURSE_ID)
            db.add(row)
        row.position, row.title_en, row.title_ta, row.body_en, row.body_ta, row.duration_min = i, ten, tta, ben, bta, mins
    db.flush()
