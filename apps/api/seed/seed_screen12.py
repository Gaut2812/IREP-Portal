"""Screen 12 seed: readiness config, skill scores, snapshots, badges, events.

Skill scores are solved so that the weighted readiness formula reproduces
each student's seeded readiness_score (Priya gets the exact PDF 2 values),
so the dashboard, trainer and college aggregates stay consistent.
"""
import datetime
import random
from typing import Dict

from sqlalchemy import select

from models.schema import (
    Badge, Event, ReadinessConfig, ReadinessSnapshot, SkillScore, Student, StudentBadge,
)
from services.readiness import DEFAULT_WEIGHTS, SKILL_LABELS, band_for, compute_breakdown

PRIYA_SKILLS = {"dsa": 78, "aptitude": 71, "cloud": 64, "track": 82, "future_skills": 58, "communication": 69}
SKILL_ORDER = ["dsa", "aptitude", "cloud", "track", "future_skills", "communication"]

BADGES = [
    ("badge_cloud_deployer", "Cloud Deployer", "கிளவுட் டிப்ளாயர்", "Deployed first app on cloud", "முதல் ஆப்பை கிளவுடில் வெளியிட்டார்", "🚀", "first_cloud_deploy"),
    ("badge_dsa_master", "DSA Master", "DSA மாஸ்டர்", "100+ patterns solved", "100+ வடிவங்கள் தீர்க்கப்பட்டன", "🧩", "problems_solved>=100"),
    ("badge_streak_15", "Consistent 15", "தொடர் 15", "15-day practice streak", "15 நாள் தொடர் பயிற்சி", "🔥", "streak>=15"),
    ("badge_team_lead", "Team Lead", "அணித் தலைவர்", "Sprint 1 shipped as lead", "ஸ்பிரிண்ட் 1 தலைவராக முடித்தார்", "👥", "sprint_lead"),
    ("badge_attendance_star", "Attendance Star", "வருகை நட்சத்திரம்", "90%+ attendance this semester", "இந்தப் பருவத்தில் 90%+ வருகை", "⭐", "attendance>=90"),
]


def _skills_for_score(score: int, attendance: int, rng: random.Random) -> Dict[str, int]:
    """Pick six skill values whose weighted sum (with attendance) rounds to `score`."""
    w = DEFAULT_WEIGHTS
    skills = {}
    for key in ["dsa", "aptitude", "cloud", "track", "future_skills"]:
        skills[key] = max(20, min(100, score + rng.randint(-12, 12)))
    fixed = sum(skills[k] * w[k] for k in skills) + attendance * w["attendance"]
    comm = (score - fixed) / w["communication"]
    skills["communication"] = int(max(0, min(100, round(comm))))
    return skills


def _next_weekday(today: datetime.date, weekday: int, min_days: int = 1) -> datetime.date:
    """Next date with the given weekday (0=Mon) at least min_days away."""
    d = today + datetime.timedelta(days=min_days)
    while d.weekday() != weekday:
        d += datetime.timedelta(days=1)
    return d


def demo_event_dates(today: datetime.date) -> dict:
    """Demo calendar relative to today: mirrors the PDF spacing (test on Saturday,
    interview midweek, exam in ~5 days, demo day in ~2 weeks, review the week after)."""
    sat = _next_weekday(today, 5, 2)
    wed = _next_weekday(today, 2, 1)
    demo = _next_weekday(today, 5, 9)

    def dt(d, h, m=0):
        return datetime.datetime(d.year, d.month, d.day, h, m)

    return {
        "evt_midterm_dsa": dt(sat, 10),
        "evt_mock_interview_priya": dt(wed, 16),
        "evt_aws_exam_priya": dt(today + datetime.timedelta(days=5), 9),
        "evt_mock_drive_1": dt(today + datetime.timedelta(days=9), 9),
        "evt_demo_day": dt(demo, 10),
        "evt_parent_review": dt(demo + datetime.timedelta(days=7), 10, 30),
        "evt_guest_gcc": dt(demo + datetime.timedelta(days=14), 15),
    }


def rebase_demo_dates(db, college_id: str = "col_demo_001", today: datetime.date = None) -> int:
    """Re-anchor the seeded demo events and Priya's scheduled exam to today.
    Runs on every seed so a demo database never shows a stale calendar."""
    from models.schema import Certificate
    today = today or datetime.date.today()
    dates = demo_event_dates(today)
    changed = 0
    for eid, when in dates.items():
        ev = db.execute(select(Event).filter_by(id=eid, college_id=college_id)).scalar_one_or_none()
        if ev and ev.starts_at != when:
            ev.starts_at = when
            ev.ends_at = when + datetime.timedelta(hours=3) if eid == "evt_demo_day" else None
            changed += 1
    cert = db.execute(select(Certificate).filter_by(id="cert_priya_aws_sched")).scalar_one_or_none()
    exam_day = dates["evt_aws_exam_priya"].date()
    if cert and cert.exam_date != exam_day:
        cert.exam_date = exam_day
        changed += 1
    db.flush()
    return changed


def seed_screen12(db, college_id: str = "col_demo_001") -> int:
    if db.execute(select(ReadinessSnapshot).filter_by(college_id=college_id)).first():
        return 0
    rng = random.Random(1216)
    today = datetime.date.today()

    cfg = db.execute(select(ReadinessConfig).filter_by(college_id=college_id)).scalars().first()
    if not cfg:
        db.add(ReadinessConfig(id=f"rcfg_{college_id}", college_id=college_id, weights=DEFAULT_WEIGHTS, version=1))

    for bid, name_en, name_ta, desc_en, desc_ta, icon, rule in BADGES:
        if not db.execute(select(Badge).filter_by(id=bid)).first():
            db.add(Badge(id=bid, college_id=college_id, name_en=name_en, name_ta=name_ta,
                         description_en=desc_en, description_ta=desc_ta, icon=icon, rule=rule))
    db.flush()

    students = db.execute(select(Student).filter_by(college_id=college_id)).scalars().all()
    count = 0
    priya = next((s for s in students if s.id == "std_priya_01"), None)
    if priya:  # PDF 2 baseline, immune to test-suite drift
        priya.readiness_score, priya.readiness_band, priya.readiness_delta, priya.attendance_pct = 74, "Nearly Ready", 6, 92
    for st in students:
        skills = dict(PRIYA_SKILLS) if st.id == "std_priya_01" else _skills_for_score(st.readiness_score, st.attendance_pct, rng)
        for i, key in enumerate(SKILL_ORDER):
            db.add(SkillScore(
                id=f"ss_{st.id}_{key}"[:64], college_id=college_id, student_id=st.id, skill_key=key,
                label_en=SKILL_LABELS[key]["en"], label_ta=SKILL_LABELS[key]["ta"],
                percentage=skills[key], color=SKILL_LABELS[key]["color"], sort_order=i,
            ))
        breakdown = compute_breakdown(skills, st.attendance_pct, DEFAULT_WEIGHTS)
        # last month's snapshot + today's snapshot so the dashboard can show "+6 this month"
        db.add(ReadinessSnapshot(
            id=f"rs_prev_{st.id}"[:64], college_id=college_id, student_id=st.id,
            snapshot_date=today - datetime.timedelta(days=30), score=st.readiness_score - st.readiness_delta,
            band=band_for(st.readiness_score - st.readiness_delta), delta=0, breakdown=[], config_version=1,
        ))
        db.add(ReadinessSnapshot(
            id=f"rs_now_{st.id}"[:64], college_id=college_id, student_id=st.id,
            snapshot_date=today, score=st.readiness_score, band=st.readiness_band,
            delta=st.readiness_delta, breakdown=breakdown, config_version=1,
        ))
        # badges by rule
        earned = []
        if st.problems_solved >= 100:
            earned.append("badge_dsa_master")
        if st.streak_days >= 15:
            earned.append("badge_streak_15")
        if st.attendance_pct >= 90:
            earned.append("badge_attendance_star")
        if st.id == "std_priya_01":  # PDF 2: "Latest: Cloud Deployer"
            earned = ["badge_cloud_deployer", "badge_team_lead"] + earned
        for j, bid in enumerate(dict.fromkeys(earned)):
            db.add(StudentBadge(id=f"sb_{st.id}_{bid}"[:64], college_id=college_id, student_id=st.id, badge_id=bid,
                                earned_on=today - datetime.timedelta(days=3 + 7 * j)))
        count += 1
    db.flush()

    # Events (shared with screens 15/19), dated relative to today so the demo never goes stale
    if not db.execute(select(Event).filter_by(college_id=college_id)).first():
        aids_batch = "bat_aids_s5_aids"
        d = demo_event_dates(today)
        events = [
            Event(id="evt_midterm_dsa", college_id=college_id, title_en="Mid-term DSA test", title_ta="இடைப்பருவ DSA தேர்வு", kind="test",
                  starts_at=d["evt_midterm_dsa"], audience="students", batch_id=aids_batch, location="Online · Practice Tests"),
            Event(id="evt_mock_interview_priya", college_id=college_id, title_en="Mock interview", title_ta="மாதிரி நேர்காணல்", kind="interview",
                  starts_at=d["evt_mock_interview_priya"], audience="students", student_id="std_priya_01", location="Interview room 2"),
            Event(id="evt_aws_exam_priya", college_id=college_id, title_en="AWS Cloud Practitioner", title_ta="AWS கிளவுட் பிராக்டிஷனர்", kind="exam",
                  starts_at=d["evt_aws_exam_priya"], audience="students", student_id="std_priya_01", location="Pearson VUE centre"),
            Event(id="evt_mock_drive_1", college_id=college_id, title_en="Mock Drive 1 · Sem 7", title_ta="மாதிரி டிரைவ் 1 · பருவம் 7", kind="drive",
                  starts_at=d["evt_mock_drive_1"], audience="college", location="Seminar hall"),
            Event(id="evt_demo_day", college_id=college_id, title_en="Project Demo Day", title_ta="புராஜெக்ட் டெமோ தினம்", kind="demo_day",
                  starts_at=d["evt_demo_day"], ends_at=d["evt_demo_day"] + datetime.timedelta(hours=3), audience="all", location="Auditorium A & Live Stream",
                  description_en="Students present live projects. Parents are invited.", description_ta="மாணவர்கள் திட்டங்களை நேரலையில் வழங்குவர். பெற்றோர் அழைக்கப்படுகிறார்கள்.",
                  rsvp_enabled=True),
            Event(id="evt_parent_review", college_id=college_id, title_en="Parent review meeting", title_ta="பெற்றோர் ஆய்வு கூட்டம்", kind="meeting",
                  starts_at=d["evt_parent_review"], audience="parents", location="Block B conference room", rsvp_enabled=True),
            Event(id="evt_guest_gcc", college_id=college_id, title_en="Guest session: GCC leaders", title_ta="விருந்தினர் அமர்வு: GCC தலைவர்கள்", kind="guest",
                  starts_at=d["evt_guest_gcc"], audience="all", location="Auditorium A"),
        ]
        db.add_all(events)
    db.flush()
    return count
