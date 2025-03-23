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

    account_id: str = Field()
    """ the operational account id """

    twilio_sid: str | None = Field(default=None)
    twilio_auth_token: str | None = Field(default=None)

    def encode_value(self, value: str | None) -> str | None:
        """Encodes a value using Base64."""
        if value:
            return base64.b64encode(value.encode()).decode()
        return None

    def decode_value(self, value: str | None) -> str | None:
        """Decodes a Base64 encoded value."""
        if value:
            try:
                return base64.b64decode(value.encode()).decode()
            except Exception:
                return value  # Return original if decoding fails (e.g., if already decoded)
        return None


# Event listeners for automatic encoding/decoding
@event.listens_for(InboundTrunk, "before_insert")
@event.listens_for(InboundTrunk, "before_update")
def encode_twilio_details(mapper, connection, target: InboundTrunk):
    target.twilio_sid = target.encode_value(target.twilio_sid)
    target.twilio_auth_token = target.encode_value(target.twilio_auth_token)


@event.listens_for(InboundTrunk, "load")
def decode_twilio_details(target: InboundTrunk, context):
    target.twilio_sid = target.decode_value(target.twilio_sid)
    target.twilio_auth_token = target.decode_value(target.twilio_auth_token)


class PhoneNumber(SQLModel, table=True):
    __tablename__ = "phone_numbers"  # type: ignore
    phone_number: str = Field(primary_key=True)
    trunk_id: str = Field(default=None, foreign_key="inbound_trunks.trunk_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )
