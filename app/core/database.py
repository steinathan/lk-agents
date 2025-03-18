from collections.abc import Generator
from datetime import datetime, timezone
from fastapi import Depends
from typing_extensions import Annotated
from sqlmodel import Field, SQLModel, Session, create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


async def init_db() -> None:
    with Session(engine):
        # Tables should be created with Alembic migrations
        # But if you don't want to use migrations, create
        # the tables un-commenting the next lines
        # from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)


# ┌┬┐┌─┐┌┬┐┌─┐┌┐ ┌─┐┌─┐┌─┐  ┌┬┐┌─┐┌─┐┌─┐┌┐┌┌┬┐┌─┐┌┐┌┌─┐┬ ┬┬
#  ││├─┤ │ ├─┤├┴┐├─┤└─┐├┤    ││├┤ ├─┘├┤ │││ ││├┤ ││││  └┬┘│
# ─┴┘┴ ┴ ┴ ┴ ┴└─┘┴ ┴└─┘└─┘  ─┴┘└─┘┴  └─┘┘└┘─┴┘└─┘┘└┘└─┘ ┴ o


def get_session_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


class BaseTable(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


DatabaseSessionType = Annotated[Session, Depends(get_session_db)]
