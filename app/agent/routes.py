from fastapi import APIRouter, HTTPException
from loguru import logger

from app.agent.deps import AssistantServiceType
from app.agent.schema import AgentSettings

router = APIRouter(tags=["agent"], prefix="/agent")


@router.patch("/publish", status_code=201)
async def publish_agent(agent_service: AssistantServiceType, inputs: AgentSettings):
    try:
        agent = await agent_service.create_agent(inputs)
        if not agent:
            raise HTTPException(status_code=500, detail="Failed to create agent")
        return {"message": "agent created successfully", "agent": agent}
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise


@router.get("/find")
async def find_agent_by(
    agent_service: AssistantServiceType,
    agent_phone: str | None = None,
    agent_id: str | None = None,
):
    agent = await agent_service.find_agent_by(phone_number=agent_phone, id=agent_id)
    if not agent:
        raise HTTPException(status_code=501, detail="Agent not found")
    return agent
