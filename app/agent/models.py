from app.core.database import BaseTable
from app.utils import make_cuid
from sqlmodel import Column, Field
from sqlalchemy.dialects import postgresql


from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AgentModel(BaseTable, table=True):
    __tablename__: str = "agents"  # type: ignore # Explicit table name

    id: str = Field(default_factory=lambda: make_cuid("agent_"), primary_key=True)

    # Agent config
    config: dict = Field(sa_column=Column(postgresql.JSON), default_factory=dict)

    is_active: bool = Field(default=True)

    class Config:  # type: ignore
        arbitrary_types_allowed = True
