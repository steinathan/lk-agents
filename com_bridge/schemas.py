from pydantic import BaseModel


class CustomerInfo(BaseModel):
    customer_name: str | None = "N/A"
    customer_email: str | None = "N/A"
    customer_phone: str | None = "N/A"
    has_existing_ride: bool = False


class AgentLookupInputs(BaseModel):
    phone_number: str | None = None
    interaction_id: str | None = None
    agent_id: str | None = None
    customer_phone: str | None = None
