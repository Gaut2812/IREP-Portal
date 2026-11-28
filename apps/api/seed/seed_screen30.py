"""Screen 30 seed: Team Phoenix (Clinic Appointment System), sprint 2 of 3,
CR-04, stand-ups and build history. Every seed restores the PDF 6 board so
demos and end-to-end runs start from the same state."""
import datetime

from sqlalchemy import select, delete

from models.schema import (
    Team, TeamMember, Sprint, SprintTask, ChangeRequest, BuildRun, PullRequest, Student, User,
)

TEAM = "team_phoenix"
# task id -> (column, position, story points, assignee name)
BOARD = {
    "task_01": ("todo", 0, 3, "Karthik S"),
    "task_02": ("todo", 1, 2, "Meena V"),
    "task_03": ("todo", 2, 1, "Ananya P"),
    "task_04": ("in_progress", 0, 2, "Priya R"),
    "task_05": ("in_progress", 1, 2, "Rahul D"),
    "task_06": ("in_progress", 2, 2, "Karthik S"),
    "task_07": ("code_review", 0, 2, "Rahul D"),
    "task_08": ("code_review", 1, 1, "Priya R"),
    "task_09": ("done", 0, 6, "Priya R"),
    "task_10": ("done", 1, 5, "Rahul D"),
    "task_11": ("done", 2, 5, "Meena V"),
    "task_12": ("done", 3, 5, "Ananya P"),
}
TITLES = {"task_07": "JWT refresh tokens", "task_08": "Unit tests – booking service"}


def _student_by_name(db, name: str, batch_pref: str):
    rows = db.execute(select(Student).join(User, User.id == Student.user_id).where(User.name == name)).scalars().all()
    for r in rows:
        if r.batch_id == batch_pref:
            return r
    return rows[0] if rows else None


PHOENIX_DESCRIPTION = ("A web app for a neighbourhood clinic: patients book a slot online and get a token number, the "
                       "front desk sees the day's queue, and doctors see each patient's history before the visit.")
PHOENIX_GOALS = "\n".join([
    "Patients book, move or cancel an appointment in under a minute",
    "Front desk sees a live token queue for the day",
    "AI triage suggests urgency from the symptoms typed in",
    "SMS reminder 24 hours before every visit, in Tamil and English",
])


def seed_screen30(db, college_id: str = "col_demo_001") -> None:
    now = datetime.datetime.now()
    # project details on the board (added later; also filled on an existing database, only where still empty)
    team = db.get(Team, TEAM)
    if team is not None:
        team.description = team.description or PHOENIX_DESCRIPTION
        team.goals = team.goals or PHOENIX_GOALS
    if not db.execute(select(Team).filter_by(id=TEAM)).first():
        db.add(Team(id=TEAM, college_id=college_id, name="Team Phoenix", project_title="Clinic Appointment System",
                    project_id="proj_clinic_02", client_name="Trainer (Arun K.)", repo_full_name="irep-demo/clinic-appointment-system",
                    trainer_id="trn_arun_01", description=PHOENIX_DESCRIPTION, goals=PHOENIX_GOALS))
        db.flush()
        db.add(Sprint(id="sprint_phoenix_1", college_id=college_id, team_id=TEAM, number=1, total_sprints=3, ends_week=4, status="closed", velocity=30,
                      goal="Login, roles and appointment CRUD"))
        db.add(Sprint(id="sprint_phoenix_2", college_id=college_id, team_id=TEAM, number=2, total_sprints=3, ends_week=8, status="active",
                      goal="Booking flow, AI triage and patient history"))
        db.flush()
        members = {}
        for name in ["Priya R", "Rahul D", "Meena V", "Ananya P", "Karthik S"]:
            st = _student_by_name(db, name, "bat_aids_s5_aids")
            if st:
                members[name] = st
                db.add(TeamMember(id=f"tm_{TEAM}_{st.id}"[:64], college_id=college_id, team_id=TEAM, student_id=st.id,
                                  role="lead" if name == "Priya R" else "developer"))
        db.add(ChangeRequest(id="cr_phoenix_04", college_id=college_id, team_id=TEAM, sprint_id="sprint_phoenix_2", code="CR-04",
                             title="SMS reminders", description="The clinic wants an SMS reminder 24 hours before every appointment, in Tamil and English.",
                             status="accepted", task_id="task_01", raised_by="usr_arun_01"))
        for n, hours, status in [(446, 30, "failing"), (447, 26, "passing"), (448, 2, "passing")]:
            db.add(BuildRun(id=f"br_phoenix_{n}", college_id=college_id, team_id=TEAM, run_number=n, workflow="CI / deploy-staging",
                            status=status, environment="staging" if status == "passing" else None,
                            url=f"https://github.com/irep-demo/clinic-appointment-system/actions/runs/{n}",
                            finished_at=now - datetime.timedelta(hours=hours)))
        db.flush()

    # restore the PDF 6 board state on every seed
    names = {}
    for tid, (col, pos, pts, who) in BOARD.items():
        t = db.execute(select(SprintTask).filter_by(id=tid)).scalar_one_or_none()
        if not t:
            continue
        st = names.get(who) or _student_by_name(db, who, "bat_aids_s5_aids")
        names[who] = st
        t.column_name, t.position, t.story_points = col, pos, pts
        t.team_id, t.sprint_id = TEAM, "sprint_phoenix_2"
        t.assignee_student_id = st.id if st else None
        if tid in TITLES:
            t.title = TITLES[tid]
    # cards created by tests/demos (e.g. new change requests) are removed
    db.execute(delete(SprintTask).where(SprintTask.team_id == TEAM, SprintTask.id.notin_(list(BOARD))))
    db.execute(delete(ChangeRequest).where(ChangeRequest.team_id == TEAM, ChangeRequest.id != "cr_phoenix_04"))
    db.execute(delete(BuildRun).where(BuildRun.team_id == TEAM, BuildRun.id.notin_(["br_phoenix_446", "br_phoenix_447", "br_phoenix_448"])))
    latest = db.execute(select(BuildRun).filter_by(id="br_phoenix_448")).scalar_one_or_none()
    if latest:
        latest.finished_at = now - datetime.timedelta(hours=2)
    for pr_id in ("pr_39", "pr_41"):
        pr = db.execute(select(PullRequest).filter_by(id=pr_id)).scalar_one_or_none()
        if pr:
            pr.status, pr.reviewed_by, pr.reviewed_at, pr.review_feedback = "pending", None, None, None
    db.flush()
