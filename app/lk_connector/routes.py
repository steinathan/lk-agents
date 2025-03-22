from fastapi import APIRouter
from loguru import logger

from lk_twilio_connector import connect_custom_twilio_to_livekit, ConnectParams

router = APIRouter(tags=["connector"], prefix="/connector")


@router.patch("/connect", status_code=200)
async def connect_twilio(inputs: ConnectParams):
    try:
        await connect_custom_twilio_to_livekit(inputs)
        return {"message": "connected successfully"}
    except Exception as e:
        logger.error(f"Failed to connect account: {e}")
        raise


@router.delete("/disconnect", status_code=200)
async def disconnect_twilio(inputs: ConnectParams):
    try:
        return {"message": "disconnected successfully"}
    except Exception as e:
        logger.error(f"Failed to disconnect account: {e}")
        raise
