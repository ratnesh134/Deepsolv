import json
from contextlib import contextmanager
from typing import Optional
from app.db.session import SessionLocal, engine
from app.models.db_models import Base, BrandSnapshot
from app.config import settings

if settings.ENABLE_DB and engine:
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_session():
    if not settings.ENABLE_DB or SessionLocal is None:
        yield None
        return
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def save_brand_snapshot(website_url: str, payload: dict) -> Optional[int]:
    if not settings.ENABLE_DB or SessionLocal is None:
        return None
    with get_session() as s:
        snap = BrandSnapshot(website_url=website_url,
                             brand_name=payload.get("brand_name"),
                             json_payload=json.dumps(payload))
        s.add(snap)
        s.flush()
        return snap.id
