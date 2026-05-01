from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    version: int