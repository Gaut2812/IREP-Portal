"""Screen 22 seed: the IREP bank (platform tenant, link L37) with one coding problem
and one aptitude test, and demo hygiene. Re-seeding restores demo state: problems
and tests created through 22 or 46 (random ids) are removed with their cases,
questions, submissions and attempts; seeded items are published to every batch again."""
import re

from sqlalchemy import delete, select

from core.security import PLATFORM_TENANT
from models.schema import (AttemptAnswer, CodingHintUsage, CodingProblem, CodingSubmission, Notification, PracticeQuestion, PracticeTest,
                           ProctorEvent, SubmissionResult, TestAttempt, TestCase, TopicScore)

GENERATED = re.compile(r"^(prob|test)_[0-9a-f]{16}$")
BANK_PROBLEM = "bank_prob_pair_sum"
BANK_TEST = "bank_test_aptitude_core"

PAIR_SUM = ("Given n integers and a target t, print YES if two different positions add up to t, else NO.\n\n"
            "Input: the first line has n and t; the second line has n integers.")
QUESTIONS = [
    ("A train 120 m long passes a pole in 6 seconds. What is its speed in km/h?", "60", "72", "80", "90", "B", "Quantitative", "Speed"),
    ("If 6 workers finish a job in 10 days, how many days do 4 workers take?", "12", "14", "15", "16", "C", "Quantitative", "Time & Work"),
    ("Find the odd one out: 3, 5, 11, 14, 17", "5", "11", "14", "17", "C", "Reasoning", "Series"),
    ("A price rises 20% and then falls 20%. The net change is", "0%", "4% fall", "4% rise", "2% fall", "B", "Quantitative", "Percentages"),
    ("Choose the correct sentence.", "He don't like tea.", "He doesn't likes tea.", "He doesn't like tea.", "He not like tea.", "C", "Verbal", "Grammar"),
]


def _purge(db, problem_ids, test_ids):
    if problem_ids:
        subs = list(db.execute(select(CodingSubmission.id).where(CodingSubmission.problem_id.in_(problem_ids))).scalars())
        db.execute(delete(SubmissionResult).where(SubmissionResult.submission_id.in_(subs or ["_"])))
        db.execute(delete(CodingSubmission).where(CodingSubmission.problem_id.in_(problem_ids)))
        db.execute(delete(CodingHintUsage).where(CodingHintUsage.problem_id.in_(problem_ids)))
        db.execute(delete(TestCase).where(TestCase.problem_id.in_(problem_ids)))
        db.execute(delete(CodingProblem).where(CodingProblem.id.in_(problem_ids)))
    if test_ids:
        atts = list(db.execute(select(TestAttempt.id).where(TestAttempt.test_id.in_(test_ids))).scalars())
        db.execute(delete(AttemptAnswer).where(AttemptAnswer.attempt_id.in_(atts or ["_"])))
        db.execute(delete(ProctorEvent).where(ProctorEvent.attempt_id.in_(atts or ["_"])))
        db.execute(delete(TopicScore).where(TopicScore.attempt_id.in_(atts or ["_"])))
        db.execute(delete(TestAttempt).where(TestAttempt.id.in_(atts or ["_"])))
        db.execute(delete(PracticeQuestion).where(PracticeQuestion.test_id.in_(test_ids)))
        db.execute(delete(PracticeTest).where(PracticeTest.id.in_(test_ids)))


def seed_screen22(db, college_id: str = "col_demo_001") -> None:
    probs = [p for p in db.execute(select(CodingProblem.id)).scalars() if GENERATED.match(p)]
    tests = [t for t in db.execute(select(PracticeTest.id)).scalars() if GENERATED.match(t)]
    _purge(db, probs, tests)
    db.execute(delete(Notification).where(Notification.kind == "assessment"))
    for model in (CodingProblem, PracticeTest):
        for item in db.execute(select(model).where(model.college_id == college_id)).scalars():
            item.status, item.batch_ids, item.due_at = "published", None, None

    if db.get(CodingProblem, BANK_PROBLEM) is None:
        db.add(CodingProblem(id=BANK_PROBLEM, college_id=PLATFORM_TENANT, slug="pair-sum", title="Pair with a target sum", difficulty="Easy",
                             topic="Hashing", company_tags="Service cos.", week_info="", statement=PAIR_SUM,
                             example_input="4 9\n2 7 11 15", example_output="YES", constraints="1 <= n <= 10^5",
                             starter_code="def solve():\n    pass\n", starter_codes={"python": "def solve():\n    pass\n"},
                             trainer_notes="Start with a set of seen values; ask students why sorting is O(n log n).", trainer_author="IREP",
                             status="published", batch_ids=None))
        db.flush()
        for i, (name, inp, out, hidden) in enumerate([("Sample", "4 9\n2 7 11 15", "YES", False), ("No pair", "3 10\n1 2 3", "NO", True),
                                                       ("Same value twice", "2 8\n4 4", "YES", True)], start=1):
            db.add(TestCase(id=f"tc_{BANK_PROBLEM}_{i}", college_id=PLATFORM_TENANT, problem_id=BANK_PROBLEM, test_order=i,
                            is_hidden=hidden, name=name, input_data=inp, expected_output=out))
    if db.get(PracticeTest, BANK_TEST) is None:
        db.add(PracticeTest(id=BANK_TEST, college_id=PLATFORM_TENANT, title="Aptitude core: 5 questions", category="Service Company Pattern · Aptitude",
                            duration_min=10, total_questions=len(QUESTIONS), sections_json={"Quantitative": 3, "Reasoning": 1, "Verbal": 1},
                            status="published", batch_ids=None))
        db.flush()
        for i, (q, a, b, c, d, ok, sec, topic) in enumerate(QUESTIONS, start=1):
            db.add(PracticeQuestion(id=f"pq_{BANK_TEST}_{i}", college_id=PLATFORM_TENANT, test_id=BANK_TEST, question_number=i,
                                    section_name=sec, topic=topic, question_text=q, option_a=a, option_b=b, option_c=c, option_d=d,
                                    correct_option=ok))
    db.flush()
