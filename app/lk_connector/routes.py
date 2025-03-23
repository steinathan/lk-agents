from fastapi import APIRouter
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.database import DatabaseSessionType
from lk_twilio_connector import connect_custom_twilio_to_livekit, ConnectParams

router = APIRouter(tags=["connector"], prefix="/connector")


@router.patch("/connect", status_code=200)
async def connect_twilio(session: DatabaseSessionType, inputs: ConnectParams):
    try:
        await connect_custom_twilio_to_livekit(session, inputs)
        return {"message": f"{inputs.phone_number} is connected successfully"}
    except Exception as e:
        logger.exception(f"Failed to connect account: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.delete("/disconnect", status_code=200)
async def disconnect_twilio(inputs: ConnectParams):
    try:
        return {"message": "disconnected successfully"}
    except Exception as e:
        logger.error(f"Failed to disconnect account: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
