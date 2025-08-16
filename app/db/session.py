from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = None
SessionLocal = None

if settings.ENABLE_DB and settings.DATABASE_URL:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
