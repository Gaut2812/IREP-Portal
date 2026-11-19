"""Deterministic cohort seed (S0 foundation).

Creates branches, batches, trainers, 612 students with users, parents,
certificates, internships and attendance so that the trainer and college
dashboards aggregate live from rows and still land on the mockup figures
(612 students over 4 branches, 184 certifications, 73 internships, batch
readiness 82/76/71/79/68, branch attendance 91/88/90/86).

The generator uses a fixed random seed, so every fresh database gets the
same cohort and the tests can assert on it.
"""
import datetime
import hashlib
import random
from typing import Dict, List

from sqlalchemy import select

from core.security import get_password_hash
from models.schema import (
    Branch, Batch, BatchTrainer, Student, Trainer, User, ParentStudent,
    Certificate, Internship, SessionItem, SessionAttendance,
)

RNG_SEED = 20261116
YEAR = "2026-27"

FIRST_NAMES = [
    "Aarav", "Abinaya", "Akash", "Anitha", "Arjun", "Bhavana", "Chandru", "Deepak", "Deepika", "Dinesh",
    "Gayathri", "Gokul", "Harini", "Hari", "Ishwarya", "Jeeva", "Kavya", "Keerthana", "Kiran", "Kumar",
    "Lakshmi", "Lokesh", "Madhan", "Mahalakshmi", "Manoj", "Meena", "Mohan", "Naveen", "Nithya", "Pavithra",
    "Prakash", "Pradeep", "Priyanka", "Raghav", "Ramya", "Ravi", "Revathi", "Sanjay", "Santhosh", "Saranya",
    "Sathish", "Shalini", "Shruthi", "Siva", "Sowmya", "Srinivas", "Sudha", "Suresh", "Swathi", "Tamil",
    "Thamizh", "Uma", "Varun", "Vignesh", "Vijay", "Vinoth", "Yamuna", "Yogesh", "Nandhini", "Karthika",
]
LAST_INITIALS = ["S", "K", "R", "M", "V", "P", "N", "D", "A", "B", "G", "J", "L", "T"]

# Branch definitions: id, name, code, track, students per semester 2..7
BRANCHES = [
    ("br_cse", "CSE", "CSE", "Software Engineering", {2: 30, 3: 25, 4: 25, 5: 100, 6: 38, 7: 10}),      # 228
    ("br_it", "IT", "IT", "Software Engineering", {2: 30, 3: 26, 4: 48, 5: 20, 6: 30, 7: 10}),            # 164
    ("br_aids", "AI & DS", "AIDS", "AI & Data Science", {2: 20, 3: 16, 4: 8, 5: 50, 6: 36, 7: 12}),       # 142
    ("br_cyb", "Cybersecurity", "CYB", "Cybersecurity", {2: 8, 3: 6, 4: 4, 5: 50, 6: 8, 7: 2}),           # 78
]
BRANCH_SCORE_TARGET = {"br_cse": 78, "br_it": 73, "br_aids": 77, "br_cyb": 70}
BRANCH_ATTENDANCE_TARGET = {"br_cse": 91, "br_it": 88, "br_aids": 90, "br_cyb": 86}

# Trainer Arun's five batches (PDF 8): short name -> (branch, semester, size, readiness target)
ARUN_BATCHES = {
    "CSE-A": ("br_cse", 5, 50, 82),
    "CSE-B": ("br_cse", 5, 50, 76),
    "IT-A": ("br_it", 4, 48, 71),
    "AI&DS": ("br_aids", 5, 50, 79),
    "Cyber": ("br_cyb", 5, 50, 68),
}

EXTRA_TRAINERS = [
    ("usr_meena_01", "trn_meena_01", "Meena S", "meena.s@demo.edu", "MS", "Technical Trainer", "Machine Learning"),
    ("usr_pooja_01", "trn_pooja_01", "Pooja M", "pooja.m@demo.edu", "PM", "Aptitude Trainer", "Aptitude & Reasoning"),
    ("usr_sid_01", "trn_sid_01", "Siddharth R", "siddharth.r@demo.edu", "SR", "Communication Trainer", "GD & Communication"),
]

# Named students that other screens refer to: name -> (batch short, score, attendance)
NAMED_STUDENTS = {
    "Karthik S": ("CSE-B", 52, 71),
    "Divya M": ("IT-A", 56, 82),
    "Rahul V": ("Cyber", 58, 78),
    "Sneha N": ("AI&DS", 81, 94),
    "Vikram R": ("AI&DS", 84, 95),
    "Ananya P": ("AI&DS", 79, 93),
    "Meena V": ("AI&DS", 77, 90),
    "Rahul D": ("AI&DS", 80, 91),
}

CERT_TITLES = [
    ("AWS Cloud Practitioner", "Amazon Web Services", "exam"),
    ("Google Data Analytics", "Google", "external"),
    ("Microsoft Azure Fundamentals (AZ-900)", "Microsoft", "exam"),
    ("Docker Certified Associate", "Docker", "external"),
    ("IREP Course: DSA Patterns", "IREP", "course"),
    ("IREP Course: Cloud & DevOps", "IREP", "course"),
]
CERT_MONTHLY = [(6, 28), (7, 26), (8, 38), (9, 51), (10, 41)]   # cumulative 28/54/92/143/184
INTERNSHIP_COMPANIES = ["Zoho", "Freshworks", "TCS", "Infosys", "Wipro", "HCLTech", "Cognizant", "Kaar Tech", "Chargebee", "Mindtree"]


def band_for(score: int) -> str:
    if score >= 75:
        return "Placement Ready"
    if score >= 60:
        return "Nearly Ready"
    return "Needs Support"


def _nudge_to_mean(values: List[int], target_mean: float, lo: int, hi: int, locked: set) -> None:
    """Deterministically shift values (in place) until the mean hits target."""
    if not values:
        return
    for _ in range(100000):
        current = sum(values) / len(values)
        if abs(current - target_mean) < 0.05:
            return
        step = 1 if current < target_mean else -1
        moved = False
        for i in range(len(values)):
            if i in locked:
                continue
            nv = values[i] + step
            if lo <= nv <= hi:
                values[i] = nv
                moved = True
                if abs(sum(values) / len(values) - target_mean) < 0.05:
                    return
        if not moved:
            return


def seed_cohort(db, college_id: str = "col_demo_001") -> int:
    """Seed the cohort if branches do not exist yet. Returns students created."""
    if db.execute(select(Branch).filter_by(college_id=college_id)).first():
        return 0

    rng = random.Random(RNG_SEED)
    shared_hash = get_password_hash("password123")

    # 1. Branches
    branch_rows: Dict[str, Branch] = {}
    for bid, name, code, track, _ in BRANCHES:
        hod = "Dr. " + rng.choice(FIRST_NAMES) + " " + rng.choice(LAST_INITIALS)
        b = Branch(id=bid, college_id=college_id, name=name, code=code, track=track, hod_name=hod)
        branch_rows[bid] = b
        db.add(b)

    # 2. Trainers (Arun exists)
    trainer_ids = ["trn_arun_01"]
    for uid, tid, name, email, initials, designation, spec in EXTRA_TRAINERS:
        if not db.execute(select(User).filter_by(id=uid)).first():
            db.add(User(id=uid, college_id=college_id, email=email, hashed_password=shared_hash, role="trainer",
                        name=name, phone="98765" + str(rng.randint(10000, 99999)), avatar_initials=initials, language_pref="en"))
    db.flush()  # users must exist before trainer profiles reference them
    for uid, tid, name, email, initials, designation, spec in EXTRA_TRAINERS:
        if not db.execute(select(Trainer).filter_by(id=tid)).first():
            db.add(Trainer(id=tid, college_id=college_id, user_id=uid, designation=designation, specialization=spec))
        trainer_ids.append(tid)
    db.flush()

    # 3. Batches: one per branch+semester, with Arun's named batches carved out of the matrix
    batches: Dict[str, Batch] = {}
    batch_capacity: Dict[str, int] = {}
    batch_targets: Dict[str, int] = {}
    for bid, name, code, track, per_sem in BRANCHES:
        for sem, count in per_sem.items():
            remaining = count
            arun_here = [(short, spec) for short, spec in ARUN_BATCHES.items() if spec[0] == bid and spec[1] == sem]
            for short, (_, _, size, target) in arun_here:
                slug = short.lower().replace("&", "").replace("-", "")
                batch_id = "bat_" + code.lower() + "_s" + str(sem) + "_" + slug
                batches[short] = Batch(id=batch_id, college_id=college_id, branch_id=bid, name=short + " · Sem " + str(sem),
                                       short_name=short, semester=sem, academic_year=YEAR, track=track)
                batch_capacity[short] = size
                batch_targets[short] = target
                remaining -= size
            if remaining > 0:
                short = code + "-S" + str(sem)
                batches[short] = Batch(id="bat_" + code.lower() + "_s" + str(sem), college_id=college_id, branch_id=bid,
                                       name=code + " · Sem " + str(sem), short_name=short, semester=sem, academic_year=YEAR, track=track)
                batch_capacity[short] = remaining
    for b in batches.values():
        db.add(b)
    db.flush()

    # Batch <-> trainer mapping: Arun owns his five, the rest rotate among the other trainers
    other_trainers = trainer_ids[1:]
    for i, (short, b) in enumerate(batches.items()):
        tid = "trn_arun_01" if short in ARUN_BATCHES else other_trainers[i % len(other_trainers)]
        db.add(BatchTrainer(id="bt_" + b.id, college_id=college_id, batch_id=b.id, trainer_id=tid, role="primary"))

    # 4. Students
    created = 0
    students_by_batch: Dict[str, List[Student]] = {s: [] for s in batches}
    batch_of_student: Dict[str, str] = {}
    used_emails = set()
    name_pool = [(f, l) for f in FIRST_NAMES for l in LAST_INITIALS]
    rng.shuffle(name_pool)
    name_iter = iter(name_pool)
    reg_counter = {bid: 0 for bid, *_ in BRANCHES}

    def next_name():
        f, l = next(name_iter)
        return f + " " + l

    named_remaining = dict(NAMED_STUDENTS)
    pending_students: list = []

    # Priya is already seeded: attach her to AI&DS Sem 5 batch
    priya = db.execute(select(Student).filter_by(id="std_priya_01")).scalar_one_or_none()
    if priya:
        priya.branch_id = "br_aids"
        priya.batch_id = batches["AI&DS"].id
        priya.track = "AI & Data Science"
        priya.academic_year = YEAR
        priya.readiness_score, priya.readiness_band, priya.readiness_delta = 74, "Nearly Ready", 6
        priya.attendance_pct, priya.streak_days = 92, 19
        students_by_batch["AI&DS"].append(priya)
        batch_of_student[priya.id] = "AI&DS"

    def make_student(short: str, full_name: str, score: int, attendance: int, idx: int) -> Student:
        b = batches[short]
        bid = b.branch_id
        code = branch_rows[bid].code
        reg_counter[bid] += 1
        first, last = full_name.split(" ", 1)
        base_email = first.lower() + "." + last.lower()
        email = base_email + "@demo.edu"
        n = 1
        while email in used_emails:
            n += 1
            email = base_email + str(n) + "@demo.edu"
        used_emails.add(email)
        stem = code.lower() + "_" + str(b.semester) + "_" + str(idx).zfill(3)
        # deterministic (not uuid4) so every fresh database gets the same ids;
        # hashed rather than drawn from rng so the cohort figures are unchanged
        suffix = stem + "_" + hashlib.sha1((college_id + ":" + b.id + ":" + stem).encode()).hexdigest()[:4]
        uid = "usr_" + suffix
        sid = "std_" + suffix
        user = User(id=uid, college_id=college_id, email=email, hashed_password=shared_hash, role="student",
                    name=full_name, phone="9" + str(rng.randint(100000000, 999999999)),
                    avatar_initials=(first[0] + last[0]).upper(), language_pref=rng.choice(["en", "en", "ta"]))
        db.add(user)
        pending_students.append(True)
        reg_no = "9100" + str(22 - (b.semester // 2)) + code[:2].upper() + str(reg_counter[bid]).zfill(4)
        st = Student(
            id=sid, college_id=college_id, user_id=uid,
            register_no=reg_no,
            branch=branch_rows[bid].name, semester=b.semester, batch_name=b.name,
            readiness_score=score, readiness_band=band_for(score), readiness_delta=rng.randint(-3, 8),
            problems_solved=max(10, int(score * 3.2 + rng.randint(-40, 40))),
            attendance_pct=attendance, streak_days=rng.randint(0, 27),
            branch_id=bid, batch_id=b.id, track=b.track, academic_year=YEAR,
        )
        pending_students[-1] = st
        students_by_batch[short].append(st)
        batch_of_student[sid] = short
        return st

    named_rows: Dict[str, Student] = {}
    for short, b in batches.items():
        target_n = batch_capacity[short] - len(students_by_batch[short])
        idx = 0
        for name, (nb, nscore, natt) in list(named_remaining.items()):
            if nb == short and idx < target_n:
                idx += 1
                named_rows[name] = make_student(short, name, nscore, natt, idx)
                named_remaining.pop(name)
                created += 1
        while idx < target_n:
            idx += 1
            score = int(max(40, min(97, rng.gauss(BRANCH_SCORE_TARGET[b.branch_id], 16))))
            att = rng.randint(72, 98)
            make_student(short, next_name(), score, att, idx)
            created += 1
    db.flush()  # all student users first, then the student profiles that reference them
    db.add_all([st for st in pending_students if st is not True])
    db.flush()

    # 5. Calibrate readiness and attendance means
    locked_ids = {s.id for s in named_rows.values()} | ({"std_priya_01"} if priya else set())
    for short, target in batch_targets.items():
        rows = students_by_batch[short]
        vals = [s.readiness_score for s in rows]
        locked = {i for i, s in enumerate(rows) if s.id in locked_ids}
        _nudge_to_mean(vals, target, 40, 97, locked)
        for s, v in zip(rows, vals):
            s.readiness_score = v
            s.readiness_band = band_for(v)
    for bid, *_ in BRANCHES:
        rows = [s for short, lst in students_by_batch.items() for s in lst if batches[short].branch_id == bid]
        # readiness: adjust only students outside Arun's calibrated batches
        free = [s for s in rows if batch_of_student[s.id] not in ARUN_BATCHES]
        fixed_sum = sum(s.readiness_score for s in rows if batch_of_student[s.id] in ARUN_BATCHES)
        if free:
            need_mean = (BRANCH_SCORE_TARGET[bid] * len(rows) - fixed_sum) / len(free)
            vals = [s.readiness_score for s in free]
            locked = {i for i, s in enumerate(free) if s.id in locked_ids}
            _nudge_to_mean(vals, max(40, min(97, need_mean)), 40, 97, locked)
            for s, v in zip(free, vals):
                s.readiness_score = v
                s.readiness_band = band_for(v)
        vals = [s.attendance_pct for s in rows]
        locked = {i for i, s in enumerate(rows) if s.id in locked_ids}
        _nudge_to_mean(vals, BRANCH_ATTENDANCE_TARGET[bid], 55, 100, locked)
        for s, v in zip(rows, vals):
            s.attendance_pct = v

    # 6. Parents: Lakshmi S -> Karthik S (second parent for sibling/tenant tests)
    karthik = named_rows.get("Karthik S")
    if karthik and not db.execute(select(User).filter_by(id="usr_lakshmi_01")).first():
        db.add(User(id="usr_lakshmi_01", college_id=college_id, email="lakshmi.s@example.com", hashed_password=shared_hash,
                    role="parent", name="Mrs. Lakshmi S", phone="9876543214", avatar_initials="LS", language_pref="en"))
        db.flush()
        db.add(ParentStudent(id="ps_lakshmi_karthik", college_id=college_id, parent_user_id="usr_lakshmi_01",
                             student_id=karthik.id, relationship="Mother"))

    # 7. Certificates: 184 earned Jun..Oct, highest readiness first; Priya gets one course cert + scheduled AWS exam
    all_students = [s for lst in students_by_batch.values() for s in lst]
    ranked = sorted(all_students, key=lambda s: (-s.readiness_score, s.id))
    cert_idx = 0
    for month, count in CERT_MONTHLY:
        for k in range(count):
            st = ranked[cert_idx % len(ranked)]
            title, issuer, ctype = CERT_TITLES[cert_idx % len(CERT_TITLES)]
            if cert_idx == 183 and priya is not None:   # PDF 10: Priya holds one course certificate
                st = priya
            if st.id == "std_priya_01":
                title, issuer, ctype = CERT_TITLES[4]
            db.add(Certificate(
                id="cert_" + str(cert_idx).zfill(4), college_id=college_id, student_id=st.id, title=title, issuer=issuer,
                cert_type=ctype, status="earned", issued_on=datetime.date(2026, month, 1 + (k % 27)),
                verify_code="IREP-2026" + str(month).zfill(2) + "-" + str(cert_idx).zfill(4),
            ))
            cert_idx += 1
    db.add(Certificate(id="cert_priya_aws_sched", college_id=college_id, student_id="std_priya_01",
                       title="AWS Cloud Practitioner", issuer="Amazon Web Services", cert_type="exam",
                       status="scheduled", exam_date=datetime.date(2026, 11, 22)))

    # 8. Internships: 73 for semester-6 students
    sem6 = sorted([s for s in all_students if s.semester == 6], key=lambda s: (-s.readiness_score, s.id))
    for i, st in enumerate(sem6[:73]):
        db.add(Internship(id="int_" + str(i).zfill(3), college_id=college_id, student_id=st.id,
                          company=INTERNSHIP_COMPANIES[i % len(INTERNSHIP_COMPANIES)], semester=6,
                          status="secured", secured_on=datetime.date(2026, 9 + (i % 3), 1 + (i % 25))))

    # 9. Sessions for Arun's batches today (PDF 8 "Today's schedule") + attach the existing Sem 5 sessions
    now = datetime.datetime.utcnow()
    aids_batch_id = batches["AI&DS"].id
    for s in db.execute(select(SessionItem).filter_by(college_id=college_id)).scalars().all():
        if s.batch_id is None:
            s.batch_id = aids_batch_id
            s.week_no = 8
    today_sessions = [
        ("sess_today_cse_a", "CSE-A", "System design basics", 9, 0, "Attended"),
        ("sess_today_it_a", "IT-A", "SQL window functions", 14, 0, "Scheduled"),
        ("sess_today_cyber", "Cyber", "OWASP lab: XSS", 15, 30, "Scheduled"),
    ]
    for sid, short, title, hh, mm, status in today_sessions:
        if db.execute(select(SessionItem).filter_by(id=sid)).first():
            continue
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        db.add(SessionItem(id=sid, college_id=college_id, title=title, track=batches[short].track, trainer_name="Arun K.",
                           scheduled_start=start, scheduled_end=start + datetime.timedelta(hours=1), duration_min=60,
                           session_type="Live", status=status, batch_id=batches[short].id, week_no=8))
    db.flush()

    # 10. Attendance rows for past sessions of Arun's batches (deterministic from each student's attendance_pct)
    past_sessions = db.execute(
        select(SessionItem).where(SessionItem.college_id == college_id, SessionItem.scheduled_end <= now)
    ).scalars().all()
    att_rng = random.Random(RNG_SEED + 1)
    for sess in past_sessions:
        short = next((k for k, b in batches.items() if b.id == sess.batch_id), None)
        if not short:
            continue
        for st in students_by_batch[short]:
            present = att_rng.random() * 100 < st.attendance_pct
            db.add(SessionAttendance(
                id=("att_" + sess.id + "_" + st.id)[:64], college_id=college_id, session_id=sess.id, student_id=st.id,
                minutes_present=sess.duration_min if present else att_rng.randint(0, int(sess.duration_min * 0.6)),
                status="Present" if present else "Absent", marked_at=sess.scheduled_end,
            ))
    db.flush()
    return created
