import base64
from datetime import datetime
from sqlmodel import Field, SQLModel
from sqlalchemy import event


class InboundTrunk(SQLModel, table=True):
    __tablename__ = "inbound_trunks"  # type: ignore
    trunk_id: str = Field(primary_key=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    livekit_sip_trunk_id: str = Field()

    account_id: str = Field()
    """ the operational account id """

    twilio_sid: str | None = Field(default=None)
    twilio_auth_token: str | None = Field(default=None)

    sip_username: str | None = Field(default=None)
    sip_password: str | None = Field(default=None)


class OutboundTrunk(SQLModel, table=True):
    __tablename__ = "outbound_trunks"  # type: ignore

    inbound_trunk_id: str = Field(default=None, foreign_key="inbound_trunks.trunk_id")
    livekit_sip_trunk_id: str = Field(primary_key=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
    account_id: str = Field()


class PhoneNumber(SQLModel, table=True):
    __tablename__ = "phone_numbers"  # type: ignore
    phone_number: str = Field(primary_key=True)
    trunk_id: str = Field(default=None, foreign_key="inbound_trunks.trunk_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
