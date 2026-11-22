"""Screen 13/14 seed: run the at-risk rule engine once over the cohort and mark
a deterministic subset of parents as already notified."""
import datetime
import random

from sqlalchemy import select

from models.schema import AtRiskFlag, RulesConfig
from services.at_risk import run_rules, get_rules


def seed_screen13(db, college_id: str = "col_demo_001") -> int:
    if db.execute(select(AtRiskFlag).filter_by(college_id=college_id)).first():
        return 0
    get_rules(db, college_id)
    created = run_rules(db, college_id, now=datetime.datetime.utcnow())
    rng = random.Random(1317)
    flags = db.execute(select(AtRiskFlag).filter_by(college_id=college_id).order_by(AtRiskFlag.id)).scalars().all()
    for f in flags:
        if rng.random() < 0.75:
            f.parent_notified = True
            f.parent_notified_at = datetime.datetime.utcnow() - datetime.timedelta(days=rng.randint(1, 6))
    db.flush()
    return created
