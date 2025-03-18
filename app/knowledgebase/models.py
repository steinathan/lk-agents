from app.core.database import BaseTable
from app.utils import make_cuid
from sqlmodel import Field


class Knowledgebase(BaseTable, table=True):
    __tablename__: str = "knowledgebase"  # type: ignore # Explicit table name
    id: str = Field(default_factory=lambda: make_cuid("kb_"), primary_key=True)
    openai_file_id: str = Field()
