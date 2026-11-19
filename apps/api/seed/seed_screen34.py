"""Screen 34 seed: group membership, 60 days of doubt/answer history, today's
PDF 11 conversation, and Priya's unread badges (3, 5, 0, 2, 1, 0). Re-seeding
restores this state (messages, reports, reactions and mutes made by tests
or demos in these groups are removed)."""
import datetime
import random

from sqlalchemy import select, delete

from models.schema import (
    DiscussionGroup, GroupMessage, GroupMember, MessageReaction, MessageReport, ModerationAction, Student, User,
)

BATCH = "bat_aids_s5_aids"
GROUPS = {
    "grp_batch": ("batch", "graduation", None, False),
    "grp_doubts": ("track_doubts", "bot", "Post code as snippets, never share answers to graded tests. Be respectful.", False),
    "grp_dsa": ("daily_dsa", "laptop", None, False),
    "grp_team": ("team", "chart", None, False),
    "grp_placement": ("announcements", "briefcase", None, True),
    "grp_gd": ("gd", "mic", None, False),
}
MODERATORS = ["usr_arun_01", "usr_meena_01"]
HELPERS_RECENT = {"Vikram R": 23, "Ananya P": 18, "Sneha N": 14}   # + today's replies = 24 / 19 / 15
TOPICS = [
    ("Why does my random forest overfit on the crop dataset?", "Try limiting max_depth and use cross-validation to pick it."),
    ("Is accuracy the right metric for imbalanced classes?", "Use F1 or PR-AUC; accuracy hides the minority class."),
    ("How do I choose k for k-fold?", "5 or 10 is common; with small data use stratified folds."),
    ("Why is my learning curve flat?", "Check the learning rate and feature scaling first."),
    ("What does the ROC curve tell me here?", "It shows the trade-off between TPR and FPR across thresholds."),
    ("Should I one-hot encode the district column?", "Yes, or use target encoding with cross-fitting to avoid leakage."),
    ("How do embeddings differ from one-hot vectors?", "Embeddings are dense and learned; similar items end up close."),
    ("Why does my RAG answer cite the wrong chunk?", "Your chunks are too large; try 300 tokens with overlap."),
]
SEED_PREFIXES = ("msg_seed_",)
# the original PDF 11 conversation; exact ids, because runtime ids are
# "msg_" + random hex and a "msg_0" prefix would also keep some of those
SEED_IDS = {"msg_01", "msg_02", "msg_03"}


def _utc(local: datetime.datetime) -> datetime.datetime:
    return local - (datetime.datetime.now() - datetime.datetime.utcnow())


def seed_screen34(db, college_id: str = "col_demo_001") -> None:
    now_local = datetime.datetime.now()
    users = {u.name: u for u in db.execute(select(User).where(User.college_id == college_id)).scalars().all()}
    batch_students = db.execute(select(Student, User).join(User, User.id == Student.user_id).where(Student.batch_id == BATCH).order_by(Student.id)).all()
    batch_users = [u for _, u in batch_students]
    priya = users.get("Priya R")
    named_first = [u for u in batch_users if u.name in ("Priya R", "Sneha N", "Vikram R", "Ananya P", "Meena V", "Rahul D")]
    others = [u for u in batch_users if u not in named_first]

    for gid, (kind, icon, pinned, locked) in GROUPS.items():
        g = db.execute(select(DiscussionGroup).filter_by(id=gid)).scalar_one_or_none()
        if not g:
            continue
        g.kind, g.icon, g.batch_id, g.is_locked_announcement = kind, icon, BATCH, locked
        if pinned:
            g.pinned_note = pinned

    # ---- memberships (idempotent) ----
    def ensure_member(gid, user_id, role="member"):
        if not db.execute(select(GroupMember).filter_by(group_id=gid, user_id=user_id)).first():
            db.add(GroupMember(id=f"gm_{gid}_{user_id}"[:64], college_id=college_id, group_id=gid, user_id=user_id, role=role))

    team_names = ["Priya R", "Rahul D", "Meena V", "Ananya P", "Karthik S"]
    plan = {
        "grp_batch": batch_users, "grp_doubts": (named_first + others)[:42], "grp_dsa": batch_users,
        "grp_team": [users[n] for n in team_names if n in users], "grp_placement": batch_users, "grp_gd": (named_first + others)[:35],
    }
    for gid, members in plan.items():
        for u in members:
            ensure_member(gid, u.id)
        for mod in MODERATORS if gid != "grp_team" else ["usr_arun_01"]:
            ensure_member(gid, mod, "moderator")
    db.flush()

    # ---- reset demo state ----
    demo_groups = list(GROUPS)
    stray = db.execute(select(GroupMessage.id).where(GroupMessage.group_id.in_(demo_groups))).scalars().all()
    stray = [m for m in stray if not (m.startswith(SEED_PREFIXES) or m in SEED_IDS)]
    db.execute(delete(MessageReaction).where(MessageReaction.message_id.in_(stray or ["_"])))
    db.execute(delete(MessageReport).where(MessageReport.message_id.in_(stray or ["_"])))
    db.execute(delete(GroupMessage).where(GroupMessage.id.in_(stray or ["_"])))
    db.execute(delete(MessageReport).where(MessageReport.group_id.in_(demo_groups), ~MessageReport.id.like("rep_seed_%")))
    for rep in db.execute(select(MessageReport).where(MessageReport.id.like("rep_seed_%"))).scalars().all():
        rep.status = "open"   # Screen 35 moderation-queue seed
    db.execute(delete(ModerationAction).where(ModerationAction.actor_user_id.in_(MODERATORS)))
    if priya:
        db.execute(delete(MessageReaction).where(MessageReaction.user_id == priya.id))
    for m in db.execute(select(GroupMember).where(GroupMember.group_id.in_(demo_groups))).scalars().all():
        m.muted_until = None
    for msg in db.execute(select(GroupMessage).where(GroupMessage.group_id.in_(demo_groups))).scalars().all():
        msg.is_removed, msg.removed_reason = False, None
        # only the seeded trainer answers stay marked (tests/demos may mark others)
        msg.is_marked_as_answer = msg.id == "msg_03" or (msg.id.startswith("msg_seed_h") and msg.id.endswith("t"))

    # ---- doubt history (rebuilt every seed so it stays anchored to today) ----
    # "Top helpers" counts the last 30 days, so a history generated once drifts
    # out of the window as the database ages. Same RNG seed -> same rows.
    old_hist = db.execute(select(GroupMessage.id).where(GroupMessage.id.like("msg_seed_h%"))).scalars().all()
    if old_hist:
        db.execute(delete(MessageReaction).where(MessageReaction.message_id.in_(old_hist)))
        db.execute(delete(MessageReport).where(MessageReport.message_id.in_(old_hist)))
        db.execute(delete(GroupMessage).where(GroupMessage.id.in_(old_hist)))
        db.flush()
    if True:
        rng = random.Random(3434)
        helper_pool = []
        for name, n in HELPERS_RECENT.items():
            helper_pool += [name] * n
        rng.shuffle(helper_pool)
        trainer_names = {"usr_arun_01": "Arun K.", "usr_meena_01": "Meena S"}
        askers = [u for u in (named_first + others)[:42] if u.name not in HELPERS_RECENT] or batch_users
        for i in range(127):   # + today's marked answer = 128
            days_ago = 59 - (i * 59 // 127)
            q_at = now_local.replace(hour=9, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days_ago) + datetime.timedelta(minutes=rng.randint(0, 600))
            question, hint = TOPICS[i % len(TOPICS)]
            asker = askers[i % len(askers)]
            recent = days_ago < 29
            helper_name = helper_pool.pop() if recent and helper_pool else rng.choice([u.name for u in others[:10]] or ["Vikram R"])
            helper = users.get(helper_name)
            mod = MODERATORS[i % 2]
            delay = rng.randint(22, 52)
            rows = [
                (f"msg_seed_h{i:03d}q", asker, "Student", question, q_at, False),
                (f"msg_seed_h{i:03d}h", helper, "Student", hint, q_at + datetime.timedelta(minutes=rng.randint(3, 15)), False),
                (f"msg_seed_h{i:03d}t", users.get("Arun Kumar") if mod == "usr_arun_01" else users.get("Meena S"), "Trainer",
                 "Good discussion. " + hint, q_at + datetime.timedelta(minutes=delay), True),
            ]
            for mid, u, role, text, at, answer in rows:
                if u is None:
                    continue
                name = trainer_names.get(u.id, u.name)
                db.add(GroupMessage(id=mid, college_id=college_id, group_id="grp_doubts", sender_user_id=u.id, sender_name=name, sender_role=role,
                                    sender_initials=u.avatar_initials, message_text=text, is_marked_as_answer=answer, reactions_count=0,
                                    timestamp_str=at.strftime("%I:%M %p").lstrip("0"), created_at=_utc(at), updated_at=_utc(at)))
        db.flush()

    # ---- today's PDF 11 conversation + unread messages ----
    today = now_local.replace(second=0, microsecond=0)
    base = today.replace(hour=10, minute=24) if today.hour >= 11 else today - datetime.timedelta(minutes=40)
    convo = {
        "msg_01": ("Sneha N", base),
        "msg_02": ("Vikram R", base + datetime.timedelta(minutes=4)),
        "msg_03": ("Arun Kumar", base + datetime.timedelta(minutes=11)),
    }
    for mid, (name, at) in convo.items():
        msg = db.execute(select(GroupMessage).filter_by(id=mid)).scalar_one_or_none()
        u = users.get(name)
        if msg and u:
            msg.sender_user_id = u.id
            msg.created_at = msg.updated_at = _utc(at)
            msg.timestamp_str = at.strftime("%I:%M %p").lstrip("0")
    extra = [
        ("msg_seed_d01", "grp_doubts", "Ananya P", "Student", "Also check if your test split leaks dates; use a time-based split.", 13),
        ("msg_seed_d02", "grp_doubts", "Sneha N", "Student", "Thanks! Moving the scaler into a Pipeline fixed it, CV is 0.81 now.", 16),
        ("msg_seed_b01", "grp_batch", "Arun Kumar", "Trainer", "Slides for the RAG session are uploaded in My Courses.", -60),
        ("msg_seed_b02", "grp_batch", "Arun Kumar", "Trainer", "Saturday lab starts at 10:00 in Lab 3. Bring your laptop charger.", -50),
        ("msg_seed_b03", "grp_batch", "Arun Kumar", "Trainer", "Weekly quiz moves to Friday 2 PM.", -40),
        ("msg_seed_s01", "grp_dsa", "Arun Kumar", "Trainer", "Today: Union-Find drill. Solve 'Number of Connected Components' in the Coding Lab.", -180),
        ("msg_seed_t01", "grp_team", "Karthik S", "Student", "Pushed the data cleaning script, please review.", -30),
        ("msg_seed_t02", "grp_team", "Rahul D", "Student", "Patient history API is ready on the dev branch.", -20),
        ("msg_seed_p01", "grp_placement", "Arun Kumar", "Trainer", "Mock Drive 1 registrations are open. Check Events for the date.", -90),
        ("msg_seed_g01", "grp_gd", "Meena S", "Trainer", "Topic for Friday GD: Should AI tools be allowed in exams?", -240),
    ]
    for mid, gid, name, role, text, offset in extra:
        u = users.get(name)
        if not u:
            continue
        at = base + datetime.timedelta(minutes=offset)
        msg = db.execute(select(GroupMessage).filter_by(id=mid)).scalar_one_or_none()
        display = "Arun K." if name == "Arun Kumar" else name
        if not msg:
            msg = GroupMessage(id=mid, college_id=college_id, group_id=gid, sender_user_id=u.id, sender_name=display, sender_role=role,
                               sender_initials=u.avatar_initials, message_text=text, reactions_count=0)
            db.add(msg)
        msg.created_at = msg.updated_at = _utc(at)
        msg.timestamp_str = at.strftime("%I:%M %p").lstrip("0")
    db.flush()

    # Priya's read markers -> unread badges 3 (batch), 5 (doubts), 0, 2 (team), 1 (placement), 0
    if priya:
        read_before = {
            "grp_batch": base - datetime.timedelta(minutes=61), "grp_doubts": base - datetime.timedelta(minutes=1),
            "grp_dsa": base, "grp_team": base - datetime.timedelta(minutes=31), "grp_placement": base - datetime.timedelta(minutes=91), "grp_gd": base,
        }
        for gid, at in read_before.items():
            m = db.execute(select(GroupMember).filter_by(group_id=gid, user_id=priya.id)).scalar_one_or_none()
            if m:
                m.last_read_at = _utc(at)
    # who is "online": a deterministic 18 of the doubts group seen recently
    recent = datetime.datetime.utcnow()
    doubt_members = db.execute(select(GroupMember).where(GroupMember.group_id == "grp_doubts").order_by(GroupMember.id)).scalars().all()
    # Priya counts as online (opening the group refreshes her own presence)
    doubt_members.sort(key=lambda m: 0 if priya and m.user_id == priya.id else 1)
    for i, m in enumerate(doubt_members):
        m.last_seen_at = recent if i < 18 else recent - datetime.timedelta(hours=3)
    db.flush()
