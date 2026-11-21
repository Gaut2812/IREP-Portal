"""Lab exercise checkers (labs track S13).

Browser labs run the student's SQL (PGlite) or Python (Pyodide) in the browser; the page sends
the result here and it is compared with the expected result, which never leaves the server.
Because the run happens on the student's machine these are practice checks, not graded marks
(lab results feed readiness in S15, through server-side checks).

SQL: rows are compared as strings, in order only when the exercise says `ordered`.
Python: output lines are compared after trimming trailing spaces and blank lines.
"""
from typing import List


def _cell(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def normalise_rows(rows: List[list], ordered: bool) -> List[List[str]]:
    out = [[_cell(c) for c in (r if isinstance(r, list) else [r])] for r in rows or []]
    return out if ordered else sorted(out)


def normalise_lines(text_or_lines) -> List[str]:
    lines = text_or_lines.splitlines() if isinstance(text_or_lines, str) else [str(x) for x in (text_or_lines or [])]
    lines = [ln.rstrip() for ln in lines]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def check(kit: str, expected: list, submitted, ordered: bool = False) -> bool:
    if kit == "sql":
        if not isinstance(submitted, list):
            return False
        return normalise_rows(submitted, ordered) == normalise_rows(expected, ordered)
    if kit == "python":
        return normalise_lines(submitted) == normalise_lines(expected)
    return False
