"""Readiness score engine (Screen 12 / P09).

score = Σ weight_i × component_i, where the components are the six skill
scores plus attendance. Weights and band thresholds live in `readiness_config`
per college so a college can tune them without a deploy. The nightly job is
`run_nightly` (Celery beat `irep.readiness.nightly`, 01:30 IST; also
POST /admin/jobs/readiness).
"""
import datetime
import uuid
from typing import Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from models.schema import ReadinessConfig, ReadinessSnapshot, SessionAttendance, SkillScore, Student

DEFAULT_WEIGHTS: Dict[str, float] = {
    "dsa": 0.25,
    "aptitude": 0.15,
    "cloud": 0.10,
    "track": 0.20,
    "future_skills": 0.10,
    "communication": 0.15,
    "attendance": 0.05,
}

SKILL_LABELS: Dict[str, Dict[str, str]] = {
    "dsa": {"en": "DSA patterns", "ta": "DSA வடிவங்கள்", "color": "teal"},
    "aptitude": {"en": "Aptitude & reasoning", "ta": "திறனறிவு & தர்க்கம்", "color": "blue"},
    "cloud": {"en": "Cloud & DevOps", "ta": "கிளவுட் & DevOps", "color": "purple"},
    "track": {"en": "AI & Data Science track", "ta": "AI & டேட்டா சயின்ஸ் பாதை", "color": "teal"},
    "future_skills": {"en": "Future Skills: AI engineering", "ta": "எதிர்காலத் திறன்கள்: AI பொறியியல்", "color": "orange"},
    "communication": {"en": "Communication", "ta": "தொடர்புத் திறன்", "color": "blue"},
}
COMPONENT_LABELS = {**{k: v for k, v in SKILL_LABELS.items()}, "attendance": {"en": "Attendance", "ta": "வருகை", "color": "green"}}


def get_config(db: Session, college_id: str) -> ReadinessConfig:
    cfg = db.execute(select(ReadinessConfig).filter_by(college_id=college_id)).scalars().first()
    if not cfg:
        cfg = ReadinessConfig(id=f"rcfg_{college_id}", college_id=college_id, weights=DEFAULT_WEIGHTS, version=1)
        db.add(cfg)
        db.flush()
    return cfg


def band_for(score: int, cfg: Optional[ReadinessConfig] = None) -> str:
    ready_min = cfg.band_ready_min if cfg else 75
    nearly_min = cfg.band_nearly_min if cfg else 60
    if score >= ready_min:
        return "Placement Ready"
    if score >= nearly_min:
        return "Nearly Ready"
    return "Needs Support"


def compute_breakdown(skills: Dict[str, int], attendance_pct: int, weights: Dict[str, float]) -> List[dict]:
    rows = []
    for key, weight in weights.items():
        value = attendance_pct if key == "attendance" else skills.get(key, 0)
        rows.append({
            "key": key,
            "label_en": COMPONENT_LABELS.get(key, {}).get("en", key),
            "label_ta": COMPONENT_LABELS.get(key, {}).get("ta", key),
            "value": int(value),
            "weight": weight,
            "contribution": round(value * weight, 2),
        })
    return rows


def compute_score(skills: Dict[str, int], attendance_pct: int, weights: Dict[str, float]) -> int:
    total = sum(r["contribution"] for r in compute_breakdown(skills, attendance_pct, weights))
    return int(round(total))


def latest_snapshot(db: Session, student: Student) -> Optional[ReadinessSnapshot]:
    return db.execute(
        select(ReadinessSnapshot)
        .filter_by(student_id=student.id, college_id=student.college_id)
        .order_by(ReadinessSnapshot.snapshot_date.desc(), ReadinessSnapshot.created_at.desc())
    ).scalars().first()


def student_skills(db: Session, student: Student) -> Dict[str, int]:
    rows = db.execute(select(SkillScore).filter_by(student_id=student.id, college_id=student.college_id)).scalars().all()
    return {r.skill_key: r.percentage for r in rows}


DELTA_DAYS = 30


def recompute_attendance(db: Session, student: Student) -> Optional[int]:
    """L34 attendance input: Present / (Present + Absent + Partial) over the register.
    Excused (approved leave, screen 43) is left out; trainer overrides count as finally
    marked. Returns None (and keeps the stored value) when nothing is marked yet."""
    rows = dict(db.execute(select(SessionAttendance.status, func.count(SessionAttendance.id))
                           .where(SessionAttendance.student_id == student.id, SessionAttendance.college_id == student.college_id)
                           .group_by(SessionAttendance.status)).all())
    marked = rows.get("Present", 0) + rows.get("Absent", 0) + rows.get("Partial", 0)
    if not marked:
        return None
    pct = int(round(100 * rows.get("Present", 0) / marked))
    student.attendance_pct = pct
    return pct


def _month_ago_score(db: Session, student: Student, day: datetime.date) -> Optional[int]:
    """The score about a month ago: latest snapshot on or before day - 30, else the oldest earlier one."""
    base = select(ReadinessSnapshot.score).where(ReadinessSnapshot.student_id == student.id,
                                                 ReadinessSnapshot.college_id == student.college_id)
    row = db.execute(base.where(ReadinessSnapshot.snapshot_date <= day - datetime.timedelta(days=DELTA_DAYS))
                     .order_by(ReadinessSnapshot.snapshot_date.desc())).first()
    if row is None:
        row = db.execute(base.where(ReadinessSnapshot.snapshot_date < day).order_by(ReadinessSnapshot.snapshot_date)).first()
    return row[0] if row else None


def compute_snapshot(db: Session, student: Student, snapshot_date: Optional[datetime.date] = None,
                     persist: bool = True) -> ReadinessSnapshot:
    """Today's snapshot for one student from skill_scores + attendance.
    One snapshot per student per day: a re-run the same day replaces it.
    The delta is against about a month ago ("+6 this month" on 12 and 15)."""
    cfg = get_config(db, student.college_id)
    weights = cfg.weights or DEFAULT_WEIGHTS
    day = snapshot_date or datetime.date.today()
    skills = student_skills(db, student)
    breakdown = compute_breakdown(skills, student.attendance_pct, weights)
    score = int(round(sum(r["contribution"] for r in breakdown)))
    before = _month_ago_score(db, student, day)
    delta = score - before if before is not None else 0
    snap = ReadinessSnapshot(
        id=f"rs_{uuid.uuid4().hex[:20]}",
        college_id=student.college_id,
        student_id=student.id,
        snapshot_date=day,
        score=score,
        band=band_for(score, cfg),
        delta=delta,
        breakdown=breakdown,
        config_version=cfg.version,
    )
    if persist:
        db.execute(delete(ReadinessSnapshot).where(ReadinessSnapshot.student_id == student.id,
                                                   ReadinessSnapshot.college_id == student.college_id,
                                                   ReadinessSnapshot.snapshot_date == day))
        db.add(snap)
        student.readiness_score = score
        student.readiness_band = snap.band
        student.readiness_delta = delta
    return snap


def run_readiness_job(db: Session, college_id: str) -> int:
    """Recompute one snapshot per student (no attendance recompute). Returns the count."""
    students = db.execute(select(Student).filter_by(college_id=college_id)).scalars().all()
    for st in students:
        compute_snapshot(db, st)
    db.commit()
    return len(students)


def run_nightly(db: Session, college_id: str, today: Optional[datetime.date] = None) -> dict:
    """Readiness v1 (L34), nightly per college: attendance from the register, then the
    score, band and monthly delta, then the at-risk rules on the new numbers; trainers
    hear about new flags (`at_risk.flagged`). Does not commit."""
    from services.at_risk import notify_batch_trainers, run_rules
    from services.audit import record_audit

    students = db.execute(select(Student).filter_by(college_id=college_id)).scalars().all()
    attendance = 0
    for st in students:
        if recompute_attendance(db, st) is not None:
            attendance += 1
        compute_snapshot(db, st, today)
    db.flush()
    new_flags: List = []
    run_rules(db, college_id, created_out=new_flags)
    for f in new_flags:
        record_audit(db, None, "at_risk.flagged", "at_risk_flag", f.id,
                     {"student_id": f.student_id, "reason": f.reason_key}, college_id=college_id)
    trainer_alerts = notify_batch_trainers(db, new_flags)
    return {"students": len(students), "attendance_recomputed": attendance, "flags_created": len(new_flags),
            "trainer_alerts": trainer_alerts}
