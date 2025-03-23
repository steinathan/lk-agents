from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

from app.agent.deps import AssistantServiceType
from app.agent.schema import AgentSettings, MakeOutboundCallInputs

router = APIRouter(tags=["agent"], prefix="/agent")


@router.patch("/publish", status_code=201)
async def publish_agent(agent_service: AssistantServiceType, inputs: AgentSettings):
    try:
        agent = await agent_service.create_agent(inputs)
        if not agent:
            raise HTTPException(status_code=500, detail="Failed to create agent")
        return {"message": "agent published successfully", "agent": agent}
    except Exception as e:
        logger.exception(f"Failed to create agent: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


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


@router.get("/find_all")
async def find_all_agents(
    agent_service: AssistantServiceType,
):
    agents = await agent_service.find_agents()
    return agents


@router.post("/{agent_id}/outbound_call")
async def make_call(
    agent_service: AssistantServiceType,
    inputs: MakeOutboundCallInputs,
    agent_id: str,
):
    """use the agent to make an outbound call"""
    try:
        return await agent_service.make_outbound_call(agent_id, inputs)
    except Exception as e:
        logger.exception(f"Failed to create agent: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
