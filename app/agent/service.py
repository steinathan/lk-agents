from loguru import logger
from sqlmodel import Session, select

from app.agent.models import AgentModel
from app.agent.schema import AgentSettings
from openai import OpenAI


class AssistantService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = OpenAI()

    async def create_agent(self, settings: AgentSettings) -> AgentModel:
        logger.debug(f"Creating agent with settings: {settings}")
        new_agent = AgentModel(
            is_active=True,
            config=settings.model_dump(),
        )

        # if there are configured knowledgebases, add them to the assisatn
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
