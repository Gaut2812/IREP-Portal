"""Screen 15 seed: approved monthly cards (September + October) for every
student, migrated from the legacy ParentMonthlyRecord rows for Priya."""
import datetime
import random

from sqlalchemy import select

from models.schema import MonthlyCard, Student, ParentMonthlyRecord, User

PRIYA_ROWS = [
    {"area_en": "Coding (problems solved)", "area_ta": "கோடிங் (தீர்க்கப்பட்டவை)", "prev": "252", "curr": "286", "status_en": "On track", "status_ta": "சரியான பாதையில்", "color": "green"},
    {"area_en": "Aptitude test", "area_ta": "திறனறிவுத் தேர்வு", "prev": "64%", "curr": "71%", "status_en": "Improving", "status_ta": "முன்னேற்றம்", "color": "green"},
    {"area_en": "Project", "area_ta": "புராஜெக்ட்", "prev": "Planning", "prev_ta": "திட்டமிடல்", "curr": "45% built", "curr_ta": "45% கட்டப்பட்டது", "status_en": "On track", "status_ta": "சரியான பாதையில்", "color": "green"},
    {"area_en": "Communication", "area_ta": "தொடர்புத் திறன்", "prev": "3/5", "curr": "3/5", "status_en": "Needs practice", "status_ta": "பயிற்சி தேவை", "color": "amber"},
]
PRIYA_HELP_EN = "Encourage 10 minutes of spoken English daily and ask Priya to explain her project to you at home."
PRIYA_HELP_TA = "தினமும் 10 நிமிடங்கள் ஆங்கிலத்தில் பேச ஊக்குவிக்கவும், மேலும் பிரியாவிடம் அவரது புராஜெக்ட்டை வீட்டில் விளக்கச் சொல்லுங்கள்."
PRIYA_REMARK_EN = "Consistent practice and strong ML project work. Encourage speaking practice at home."
PRIYA_REMARK_TA = "தொடர்ச்சியான பயிற்சி மற்றும் சிறந்த ML புராஜெக்ட் பணி. வீட்டில் பேச்சுப் பயிற்சியை ஊக்குவிக்கவும்."


def _rows_for(st: Student, rng: random.Random, first: str):
    prev_problems = max(0, st.problems_solved - rng.randint(10, 40))
    prev_apt = max(30, min(95, st.readiness_score - rng.randint(2, 12)))
    curr_apt = max(30, min(98, prev_apt + rng.randint(-3, 9)))
    comm = rng.choice([2, 3, 3, 4])
    return [
        {"area_en": "Coding (problems solved)", "area_ta": "கோடிங் (தீர்க்கப்பட்டவை)", "prev": str(prev_problems), "curr": str(st.problems_solved),
         "status_en": "On track" if st.problems_solved > prev_problems else "Needs practice", "status_ta": "சரியான பாதையில்" if st.problems_solved > prev_problems else "பயிற்சி தேவை",
         "color": "green" if st.problems_solved > prev_problems else "amber"},
        {"area_en": "Aptitude test", "area_ta": "திறனறிவுத் தேர்வு", "prev": f"{prev_apt}%", "curr": f"{curr_apt}%",
         "status_en": "Improving" if curr_apt > prev_apt else "Needs practice", "status_ta": "முன்னேற்றம்" if curr_apt > prev_apt else "பயிற்சி தேவை",
         "color": "green" if curr_apt > prev_apt else "amber"},
        {"area_en": "Attendance", "area_ta": "வருகை", "prev": f"{max(50, st.attendance_pct - rng.randint(0, 6))}%", "curr": f"{st.attendance_pct}%",
         "status_en": "On track" if st.attendance_pct >= 85 else "Needs attention", "status_ta": "சரியான பாதையில்" if st.attendance_pct >= 85 else "கவனம் தேவை",
         "color": "green" if st.attendance_pct >= 85 else "amber"},
        {"area_en": "Communication", "area_ta": "தொடர்புத் திறன்", "prev": f"{comm}/5", "curr": f"{comm}/5",
         "status_en": "Needs practice" if comm < 4 else "Good", "status_ta": "பயிற்சி தேவை" if comm < 4 else "நன்று", "color": "amber" if comm < 4 else "green"},
    ]


def seed_screen15(db, college_id: str = "col_demo_001") -> int:
    if db.execute(select(MonthlyCard).filter_by(college_id=college_id)).first():
        return 0
    rng = random.Random(1515)
    students = db.execute(select(Student).filter_by(college_id=college_id)).scalars().all()
    names = {u.id: u.name for u in db.execute(select(User).filter_by(college_id=college_id, role="student")).scalars().all()}
    created = 0
    for st in students:
        first = (names.get(st.user_id) or "Student").split(" ")[0]
        is_priya = st.id == "std_priya_01"
        for year, month, status in [(2026, 9, "sent"), (2026, 10, "approved")]:
            if is_priya and month == 10:
                rows, help_en, help_ta, rem_en, rem_ta = PRIYA_ROWS, PRIYA_HELP_EN, PRIYA_HELP_TA, PRIYA_REMARK_EN, PRIYA_REMARK_TA
            else:
                rows = _rows_for(st, rng, first)
                help_en = f"Ask {first} to explain one coding problem to you each weekend and encourage 10 minutes of spoken English daily."
                help_ta = f"ஒவ்வொரு வார இறுதியிலும் ஒரு கோடிங் கணக்கை விளக்கச் சொல்லி, தினமும் 10 நிமிடம் ஆங்கிலத்தில் பேச {first}-ஐ ஊக்குவிக்கவும்."
                rem_en = "Steady progress this month. Keep the practice streak going."
                rem_ta = "இந்த மாதம் நிலையான முன்னேற்றம். பயிற்சித் தொடரைத் தொடரவும்."
            approved_at = datetime.datetime(year, month + 1 if month < 12 else 12, 2, 10, 0)
            db.add(MonthlyCard(
                id=f"mc_{st.id}_{year}{month:02d}"[:64], college_id=college_id, student_id=st.id, year=year, month=month,
                rows=rows, how_to_help_en=help_en, how_to_help_ta=help_ta, trainer_remark_en=rem_en, trainer_remark_ta=rem_ta,
                trainer_name="Arun Kumar", status=status, approved_by="usr_arun_01", approved_at=approved_at,
                sent_at=approved_at + datetime.timedelta(hours=2) if status == "sent" else None,
            ))
            created += 1
    db.flush()
    return created
