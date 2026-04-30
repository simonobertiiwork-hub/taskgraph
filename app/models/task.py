from sqlalchemy import Column, Integer, String, Text
from app.db.base import Base

class Task(Base):
    __tablename__ = "tasks"

    # id задачи, автоинкремент (заполняется автоматически)
    id = Column(Integer, primary_key=True, index=True)

    # название задачи (обязательное)
    title = Column(Text, nullable=False)

    # статус задачи (new / in_progress / done)
    status = Column(String, nullable=False, default="new")