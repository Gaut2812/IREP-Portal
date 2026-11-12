import sys
from pathlib import Path

# Add the api directory (apps/api) to sys.path so local imports work
api_dir = str(Path(__file__).resolve().parent.parent)  # d:\IREP Portal\apps\api
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from seed.seed_data import init_db_and_seed

if __name__ == "__main__":
    init_db_and_seed()
