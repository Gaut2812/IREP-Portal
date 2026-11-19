#!/usr/bin/env python3
"""Link gate: every active interconnect link must have a passing test.

Reads the link table in docs/INTERCONNECT.md (section 3) and test reports:
  - pytest:     LINK_REPORT=path pytest ...   (written by apps/api/tests/conftest.py)
  - Playwright: --reporter=json output        (tests tagged "@Lxx")

Fails (exit 1) when
  - an `active` link has no passing tagged test, or any tagged test failed,
  - a test is tagged with a link ID that is not in the table,
  - the table itself is malformed (bad status, duplicate ID).

Usage:
  python scripts/link_gate.py --pytest api-links.json [--playwright e2e.json]
  python scripts/link_gate.py --list            # print the table as parsed
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "INTERCONNECT.md"
STATUSES = {"active", "planned"}
LINK_RE = re.compile(r"^L\d{2}$")


def parse_links(text: str) -> dict:
    """{id: {"status", "from", "to", "what"}} from the section-3 tables."""
    links, errors = {}, []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line.startswith("## 3.")
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not LINK_RE.match(cells[0]):
            continue
        lid, status = cells[0], cells[-1]
        if status not in STATUSES:
            errors.append(f"{lid}: status '{status}' is not one of {sorted(STATUSES)}")
        if lid in links:
            errors.append(f"{lid}: listed twice")
        links[lid] = {"status": status, "from": cells[1], "to": cells[2], "what": cells[4] if len(cells) > 4 else ""}
    if errors:
        raise SystemExit("INTERCONNECT.md is malformed:\n  " + "\n  ".join(errors))
    if not links:
        raise SystemExit("No links found in section 3 of INTERCONNECT.md")
    return links


def load_pytest(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for r in data.get("results", []):
        yield r["test"], r["links"], r["outcome"] == "passed", "pytest"


def _walk_suites(suite):
    for spec in suite.get("specs", []):
        yield spec
    for child in suite.get("suites", []):
        yield from _walk_suites(child)


def load_playwright(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for suite in data.get("suites", []):
        for spec in _walk_suites(suite):
            tags = [t.lstrip("@") for t in spec.get("tags", []) if LINK_RE.match(t.lstrip("@"))]
            if not tags:
                continue
            statuses = [res.get("status") for t in spec.get("tests", []) for res in t.get("results", [])]
            passed = bool(statuses) and statuses[-1] in ("passed",) and spec.get("ok", False)
            yield f"{spec.get('file', '?')}::{spec.get('title', '?')}", tags, passed, "playwright"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pytest", type=Path, action="append", default=[], help="pytest link report (repeatable)")
    ap.add_argument("--playwright", type=Path, action="append", default=[], help="Playwright JSON report (repeatable)")
    ap.add_argument("--doc", type=Path, default=DOC)
    ap.add_argument("--list", action="store_true", help="print the parsed table and exit")
    args = ap.parse_args()

    links = parse_links(args.doc.read_text(encoding="utf-8"))
    if args.list:
        for lid, l in sorted(links.items()):
            print(f"{lid}  {l['status']:<8} {l['from']} -> {l['to']}")
        return 0
    if not args.pytest and not args.playwright:
        ap.error("give at least one --pytest or --playwright report")

    passing, failing = defaultdict(list), defaultdict(list)
    unknown = []
    for path in args.pytest:
        rows = load_pytest(path)
        for test, tags, ok, src in rows:
            for lid in tags:
                if lid not in links:
                    unknown.append(f"{test} tags {lid}")
                (passing if ok else failing)[lid].append(f"[{src}] {test}")
    for path in args.playwright:
        for test, tags, ok, src in load_playwright(path):
            for lid in tags:
                if lid not in links:
                    unknown.append(f"{test} tags {lid}")
                (passing if ok else failing)[lid].append(f"[{src}] {test}")

    problems = []
    active = sorted(l for l, v in links.items() if v["status"] == "active")
    planned = sorted(l for l, v in links.items() if v["status"] == "planned")
    print(f"Link gate: {len(links)} links, {len(active)} active, {len(planned)} planned\n")
    for lid in active:
        n_ok, n_bad = len(passing[lid]), len(failing[lid])
        mark = "ok  " if n_ok and not n_bad else "FAIL"
        print(f"  {mark} {lid}  {n_ok} passing, {n_bad} failing  ({links[lid]['from']} -> {links[lid]['to']})")
        if not n_ok:
            problems.append(f"{lid} is active but has no passing test tagged {lid}")
        for t in failing[lid]:
            problems.append(f"{lid}: failing test {t}")
    early = [l for l in planned if passing[l]]
    if early:
        print("\n  Planned links that already have passing tests (consider marking active): " + ", ".join(early))
    for u in unknown:
        problems.append(f"unknown link ID: {u}")

    if problems:
        print("\nLink gate FAILED:")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nLink gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
