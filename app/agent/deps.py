from typing_extensions import Annotated
from app.agent.service import AssistantService
from app.core.database import DatabaseSessionType
from fastapi import Depends


def create_user_service(session: DatabaseSessionType) -> AssistantService:
    return AssistantService(session)


AssistantServiceType = Annotated[AssistantService, Depends(create_user_service)]
