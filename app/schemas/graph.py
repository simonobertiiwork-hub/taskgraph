from pydantic import BaseModel


class GraphNodeCreate(BaseModel):
    name: str


class GraphEdgeCreate(BaseModel):
    parent_id: int
    child_id: int