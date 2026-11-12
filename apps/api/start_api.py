"""
IREP Portal — API Startup Script
Run from anywhere:
  python d:\\IREP Portal\\apps\\api\\start_api.py
"""
import sys
import os
from pathlib import Path

# Add apps/api to sys.path so local imports (core.*, models.*, routers.*) resolve
API_DIR = str(Path(__file__).resolve().parent)  # d:\IREP Portal\apps\api
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

os.chdir(API_DIR)

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[API_DIR],
    )
