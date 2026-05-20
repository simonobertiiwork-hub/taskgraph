from sqlalchemy import Column, ForeignKey, Integer, Text, UniqueConstraint
from app.db.base import Base


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, index=True)  # автоинкремент
    name = Column(Text, nullable=False)                 # название вершины


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, index=True)

    parent_id = Column(
        Integer,
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )

    child_id = Column(
        Integer,
        ForeignKey("graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("parent_id", "child_id", name="uq_graph_edge"),
    )