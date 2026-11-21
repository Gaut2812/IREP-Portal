"""Check the Microsoft 365 side of live classes without creating anything (docs/deploy/TEAMS_SETUP.md).

    docker compose run --rm api python ops/teams_check.py                       # TEAMS_DEFAULT_ORGANIZER
    docker compose run --rm api python ops/teams_check.py --organizer trainer@college.edu

Each line says which admin step it proves:
  1. token      app registration, client secret            (TEAMS_SETUP.md steps 1-2)
  2. calendar   Calendars.ReadWrite consented + mailbox      (steps 3, 5)
  3. meetings   OnlineMeetings.Read.All + access policy      (steps 3, 4)
Attendance reports (OnlineMeetingArtifact.Read.All) can only be proved by a real meeting: step 8.
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from services.teams import GraphError, _upn, get_graph

HINTS = {
    "token": "check GRAPH_TENANT_ID, GRAPH_CLIENT_ID and that GRAPH_CLIENT_SECRET is the secret VALUE (not its id) and not expired",
    "calendar": "admin consent for Calendars.ReadWrite (Application) missing, or the organizer has no Exchange Online mailbox / is outside the Exchange access policy",
    "meetings": "admin consent for OnlineMeetings.Read.All (Application) missing, or the Teams application access policy is not granted to this organizer (can take up to 30 minutes)",
}


def run(organizer: str, graph=None) -> int:
    g = graph or get_graph()
    failed = 0
    checks = [
        ("token", lambda: g._access_token()),
        ("calendar", lambda: g._call("GET", f"/users/{_upn(organizer)}/events?$top=1&$select=id")),
        ("meetings", lambda: g._call("GET", f"/users/{_upn(organizer)}/onlineMeetings?$filter="
                                     + quote("JoinWebUrl eq 'https://teams.microsoft.com/l/meetup-join/irep-check'", safe=""))),
    ]
    for name, check in checks:
        try:
            check()
            print(f"ok    {name}")
        except GraphError as e:
            failed += 1
            print(f"FAIL  {name}: {e}\n      -> {HINTS[name]}")
            if name == "token":
                break
    print("all checks passed: schedule a test class (TEAMS_SETUP.md step 8)" if not failed else f"{failed} check(s) failed")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--organizer", default=settings.TEAMS_DEFAULT_ORGANIZER)
    args = ap.parse_args()
    if not args.organizer:
        print("no organizer: pass --organizer or set TEAMS_DEFAULT_ORGANIZER")
        return 2
    return run(args.organizer)


if __name__ == "__main__":
    sys.exit(main())
