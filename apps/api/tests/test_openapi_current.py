"""The committed openapi.json must match the app (definition of done).

packages/api-client is generated from it, so a stale file means a stale
client. Regenerate with:
    venv/Scripts/python -c "import json; from main import app; json.dump(app.openapi(), open('openapi.json','w',encoding='utf-8'), indent=2, ensure_ascii=False)"
"""
import json
import sys
from pathlib import Path

api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from main import app


def test_committed_openapi_matches_the_app():
    committed = json.loads((api_dir / "openapi.json").read_text(encoding="utf-8"))
    live = app.openapi()
    missing = sorted(set(live["paths"]) - set(committed["paths"]))
    extra = sorted(set(committed["paths"]) - set(live["paths"]))
    assert not missing and not extra, f"openapi.json is stale: new {missing[:5]}, removed {extra[:5]}"
    assert committed == json.loads(json.dumps(live)), "openapi.json differs from the app (schemas changed): regenerate it"
