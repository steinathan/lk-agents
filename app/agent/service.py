import json
from loguru import logger
from sqlmodel import Session, select

from app.agent.models import AgentModel
from app.agent.schema import AgentSettings, MakeOutboundCallInputs
from openai import OpenAI

from app.lk_connector.models import InboundTrunk, OutboundTrunk, PhoneNumber
from app.utils import make_cuid
from livekit import api

from app.core.config import settings


class AssistantService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = OpenAI()

    async def create_agent(self, settings: AgentSettings) -> AgentModel:
        logger.debug(f"Creating agent with settings: {settings}")

        # TODO: have a global accounts table instead of depending on trunks
        if settings.account_id is not None:
            connected_trunk = self.session.exec(
                select(InboundTrunk).where(
                    InboundTrunk.account_id == settings.account_id
                )
            ).first()

            if not connected_trunk:
                raise ValueError(
                    f"SIP trunk not found for `{settings.account_id}`, use the `/api/connector/connect` endpoint first"
                )
            if connected_trunk.account_id != settings.account_id:
                raise ValueError(
                    f"account id mismatch {connected_trunk.account_id} != {settings.account_id}"
                )

        if settings.agent_phone is not None:
            # check if phone number is already in use
            existing_agent = await self.find_agent_by(phone_number=settings.agent_phone)
            if existing_agent and settings.agent_id is None:
                raise ValueError(
                    f"Phone number {settings.agent_phone} is already assigned to agent {existing_agent.id} ({existing_agent.config.get('agent_name')})"
                )

            # if the phone number is already connected
            stmt = select(PhoneNumber).where(
                PhoneNumber.phone_number == settings.agent_phone
            )
            phone_number = self.session.exec(stmt).first()
            if not phone_number:
                raise ValueError(
                    f"Phone number {settings.agent_phone} is not connected to any account, use the `/api/connector/connect` endpoint first, then connect that number to this agent"
                )

        if not settings.agent_id:
            logger.info("Creating new agent")
            settings.agent_id = make_cuid("agent_")
            new_agent = AgentModel(
                id=settings.agent_id,
                is_active=True,
                config=settings.model_dump(),
            )

            self.session.add(new_agent)
            self.session.commit()
            self.session.refresh(new_agent)
        else:
            logger.info(f"updating agent: {settings.agent_id}")
            new_agent = await self.find_agent(settings.agent_id)
            if not new_agent:
                raise ValueError(f"Agent {settings.agent_id} not found")

            new_agent.is_active = True
            new_agent.config = settings.model_dump()
            self.session.add(new_agent)
            self.session.commit()
            self.session.refresh(new_agent)

        return new_agent

    async def find_agent(self, agent_id: str) -> AgentModel | None:
        return self.session.get(AgentModel, agent_id)

    async def find_agent_by(
        self, id: str | None = None, phone_number: str | None = None
    ) -> AgentModel | None:
        statement = select(AgentModel)
        if id:
            statement = statement.where(AgentModel.id == id)
        elif phone_number:
            statement = statement.where(
                AgentModel.config["agent_phone"].astext == phone_number
            )
        else:
            raise ValueError("Either id or phone_number must be provided")

        results = self.session.exec(statement)
        return results.first()

    async def find_agents(self) -> list[AgentModel]:
        statement = select(AgentModel)
        results = self.session.exec(statement)
        return results.fetchmany()  # type: ignore

    async def make_outbound_call(
        self, agent_id: str, inputs: MakeOutboundCallInputs
    ) -> bool:
        agent = await self.find_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # find the outbound sip trunk for the call
        account_id = agent.config["account_id"]
        if not account_id:
            raise ValueError(
                f"Agent {agent_id} is not connected to an outbound SIP trunk"
            )

        outbound_trunk = self.session.exec(
            select(OutboundTrunk).where(OutboundTrunk.account_id == account_id)
        ).first()

        if not outbound_trunk:
            raise ValueError(
                f"could not find connected outbound trunk for the account: {account_id}"
            )

        payload = {
            "agent_id": agent_id,
            "agent_name": agent.config["agent_name"],
            "sip_trunk_id": outbound_trunk.livekit_sip_trunk_id,
            "agent_phone": inputs.from_number or agent.config["agent_phone"],
            "customer_phone": inputs.to_number,
            "direction": "outbound",
        }
        logger.debug(f"Making outbound call: {payload}")

        lkapi = api.LiveKitAPI()
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=settings.LIVEKIT_AGENT_NAME,
                room=make_cuid("call-"),
                metadata=json.dumps(payload),
            )
        )
        logger.debug(f"created dispatch: {dispatch}")
        await lkapi.aclose()
        return True
