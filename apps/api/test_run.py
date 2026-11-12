import sys
sys.path.insert(0, r"d:\IREP Portal")
from sqlalchemy import create_engine
from apps.api.core.database import Base
from apps.api.models.schema import College

engine = create_engine("sqlite:///d:/IREP Portal/apps/api/irep.db", echo=False)
print("Creating all tables synchronously...", flush=True)
Base.metadata.create_all(engine)
print("Tables created successfully!", flush=True)
