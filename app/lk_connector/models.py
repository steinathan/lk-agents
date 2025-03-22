import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, create_engine, select
from twilio.rest import Client
from app.core.config import settings

from livekit import api
from livekit.protocol.sip import ListSIPInboundTrunkRequest


class InboundTrunk(SQLModel, table=True):
    __tablename__ = "inbound_trunks"  # type: ignore
    trunk_id: str = Field(primary_key=True)

    livekit_sip_trunk_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    twilio_sid: str | None = Field(default=None)
    twilio_auth_token: str | None = Field(default=None)
    active: bool = Field(default=False)


class PhoneNumber(SQLModel, table=True):
    __tablename__ = "phone_numbers"  # type: ignore
    phone_number: str = Field(primary_key=True)
    trunk_id: str = Field(default=None, foreign_key="inbound_trunks.trunk_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
