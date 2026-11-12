import sys
from pathlib import Path

# The repository root (d:\IREP Portal) is parents[3]
repo_root = str(Path(__file__).resolve().parents[3])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from apps.api.seed.seed_data import init_db_and_seed

if __name__ == "__main__":
    init_db_and_seed()
