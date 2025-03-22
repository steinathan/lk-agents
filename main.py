import multiprocessing
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any, AsyncGenerator

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from livekit.agents import (
    WorkerOptions,
    WorkerType,
    cli,
)
from loguru import logger
from app.core.database import init_db
from app.agent.runner import VoiceAgent
from app.agent.routes import router as agent_router
from app.knowledgebase.routes import router as kb_router
from app.logging import configure_pretty_logging
from app.utils import use_route_names_as_operation_ids
from app.core.config import settings

load_dotenv(dotenv_path=".env.local")

configure_pretty_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


# ╔╦╗┬┌┬┐┌┬┐┬  ┌─┐┬ ┬┌─┐┬─┐┌─┐┌─┐┬
# ║║║│ ││ │││  ├┤ │││├─┤├┬┘├┤ └─┐│
# ╩ ╩┴─┴┘─┴┘┴─┘└─┘└┴┘┴ ┴┴└─└─┘└─┘o

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ╦═╗┌─┐┬ ┬┌┬┐┌─┐┌─┐┬
# ╠╦╝│ ││ │ │ ├┤ └─┐│
# ╩╚═└─┘└─┘ ┴ └─┘└─┘o

router_prefix = "/api"

app.include_router(agent_router, prefix=router_prefix)
app.include_router(kb_router, prefix=router_prefix)


@app.get("/health")
async def hello() -> dict[str, str]:
    return {"result": "hello world"}


# ╔═╗┌┬┐┌─┐┌┬┐┬┌─┐  ┌─┐┬┬  ┌─┐┌─┐┬
# ╚═╗ │ ├─┤ │ ││    ├┤ ││  ├┤ └─┐│
# ╚═╝ ┴ ┴ ┴ ┴ ┴└─┘  └  ┴┴─┘└─┘└─┘o
# Mount static files after all routes have been added - This will be used to serve the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.exception_handler(404)
async def redirect_artboard_to_frontend(
    request: Request, exc: HTTPException
) -> HTMLResponse:
    """Redirect all 404 errors to the frontend"""
    try:
        return HTMLResponse(open(Path(__file__).parent / "static/index.html").read())
    except FileNotFoundError:
        return HTMLResponse(
            content="Consistency Violation: We can't display this page", status_code=200
        )


# add after all routes have been added
use_route_names_as_operation_ids(app)


def start_agent():
    logger.info("Starting LiveKit agent worker...")
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=VoiceAgent.entrypoint,
            prewarm_fnc=VoiceAgent.prewarm,
            worker_type=WorkerType.ROOM,
            agent_name=settings.LIVEKIT_AGENT_NAME,
        ),
    )


if __name__ == "__main__":
    # Run the LiveKit agent in a separate Python process
    # this is not the same as threading because of the GIL and signals
    agent_process = multiprocessing.Process(target=start_agent)
    agent_process.start()

    reload: bool = os.getenv("ENV", "development") == "development"
    uvicorn.run("main:app", host="0.0.0.0", port=1337, reload=reload, log_level="info")
