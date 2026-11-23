"""IREP background workers (Celery + Valkey).

The workers share the API's models and services: apps/api is put on sys.path
so there is exactly one implementation of every rule (outbox dispatch,
notification delivery, ...).
"""
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[2] / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
