from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# TODO: перевести на async (async + create_async_engine) при нагрузке
engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine)

def get_db():
    """Создать сессию БД для запроса (FastAPI сам закроет её после запроса)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()