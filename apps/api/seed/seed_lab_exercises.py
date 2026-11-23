"""Labs track S13 seed: practice exercises with checkers for the two browser labs, and hygiene.
Re-seeding restores demo state: exercise results and class spectate links in the demo college
are cleared; the exercises are upserted (fixed ids)."""
from sqlalchemy import delete, select, update

from models.schema import LabExercise, LabExerciseResult, SessionItem

MARKS_SETUP = ("CREATE TABLE IF NOT EXISTS marks (name text, score int);\n"
               "INSERT INTO marks SELECT * FROM (VALUES ('Asha', 82), ('Ravi', 74), ('Meera', 91), ('Karthik', 68)) AS v(name, score)\n"
               "WHERE NOT EXISTS (SELECT 1 FROM marks);")

EXERCISES = [
    # id, lab, position, title_en, title_ta, prompt_en, prompt_ta, setup, expected, ordered, points
    ("lex_sql_1", "lab_sql_browser", 1, "Top scorers", "அதிக மதிப்பெண் பெற்றவர்கள்",
     "Table marks(name, score) is ready. Return only the name of every student who scored 80 or more.",
     "marks(name, score) அட்டவணை தயார். 80 அல்லது அதற்கு மேல் பெற்ற மாணவர்களின் பெயரை மட்டும் காட்டவும்.",
     MARKS_SETUP, [["Asha"], ["Meera"]], False, 10),
    ("lex_sql_2", "lab_sql_browser", 2, "Count below 75", "75-க்குக் கீழ் எத்தனை",
     "Return one number: how many students scored below 75?",
     "ஒரு எண்ணை மட்டும் காட்டவும்: 75-க்குக் கீழ் எத்தனை மாணவர்கள் பெற்றனர்?",
     MARKS_SETUP, [["2"]], False, 10),
    ("lex_sql_3", "lab_sql_browser", 3, "Rank by score", "மதிப்பெண் வரிசை",
     "Return only the names, highest score first.",
     "அதிக மதிப்பெண் முதலில் வரும்படி பெயர்களை மட்டும் காட்டவும்.",
     MARKS_SETUP, [["Meera"], ["Asha"], ["Ravi"], ["Karthik"]], True, 15),
    ("lex_py_1", "lab_python_browser", 1, "Sum 1 to 10", "1 முதல் 10 வரை கூட்டல்",
     "Print the sum of the numbers 1 to 10.", "1 முதல் 10 வரையான எண்களின் கூட்டுத்தொகையை அச்சிடவும்.",
     "total = 0\n", ["55"], False, 10),
    ("lex_py_2", "lab_python_browser", 2, "Squares", "வர்க்கங்கள்",
     "Print the squares of 1 to 5, one per line.", "1 முதல் 5 வரையான எண்களின் வர்க்கங்களை வரிக்கு ஒன்றாக அச்சிடவும்.",
     "for n in range(1, 6):\n    pass\n", ["1", "4", "9", "16", "25"], False, 10),
]


def seed_lab_exercises(db, college_id: str = "col_demo_001") -> None:
    for (eid, lab, pos, ten, tta, pen, pta, setup, expected, ordered, pts) in EXERCISES:
        e = db.get(LabExercise, eid)
        if e is None:
            e = LabExercise(id=eid, college_id=college_id, lab_id=lab)
            db.add(e)
        e.position, e.title_en, e.title_ta, e.prompt_en, e.prompt_ta = pos, ten, tta, pen, pta
        e.setup, e.expected, e.ordered, e.points = setup, expected, ordered, pts
    db.flush()
    db.execute(delete(LabExerciseResult).where(LabExerciseResult.college_id == college_id))
    db.execute(update(SessionItem).where(SessionItem.college_id == college_id, SessionItem.spectate_url.is_not(None))
               .values(spectate_url=None, spectate_label=None))
    db.flush()
