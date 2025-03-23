import os

from app.logging import logger
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Literal

env_file = ".env.local"
mode = os.getenv("ENV")

if mode == "production":
    logger.info("Running in production mode:" + env_file)
    env_file = ".env.production"

logger.debug(f"Loading env file: {env_file}")

# loading env for prisma schema that don't have access to this settings class
load_dotenv(env_file)


class __Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")

    ENV: str = Field(...)

    # ╔═╗╔═╗╔═╗┬
    # ╠═╣╠═╝╠═╝│
    # ╩ ╩╩  ╩  o

    APP_NAME: str = Field("swiftai")

    # ╔╦╗┌─┐┌┬┐┌─┐┌┐ ┌─┐┌─┐┌─┐┬
    #  ║║├─┤ │ ├─┤├┴┐├─┤└─┐├┤ │
    # ═╩╝┴ ┴ ┴ ┴ ┴└─┘┴ ┴└─┘└─┘o
    DATABASE_URL: str = Field("sqlite:///database.db")

    SUPABASE_KEY: str = Field("")
    SUPABASE_URL: str = Field("")

    # ╦ ╦╦═╗╦  ╔═╗┬
    # ║ ║╠╦╝║  ╚═╗│
    # ╚═╝╩╚═╩═╝╚═╝o
    BASE_URL: str = Field(...)
    FRONTEND_URL: str = Field(...)

    # ╔╦╗┌─┐┬┬  ┌─┐┬─┐┬
    # ║║║├─┤││  ├┤ ├┬┘│
    # ╩ ╩┴ ┴┴┴─┘└─┘┴└─o
    MAILER_PROVIDER: Literal["resend", "postmark"] = "resend"

    RESEND_API_KEY: str | None = Field(None)
    RESEND_FROM_EMAIL: str | None = Field(None)

    POSTMARK_API_KEY: str | None = Field(None)

    # ╔═╗╦┬
    # ╠═╣║│
    # ╩ ╩╩o

    DEBUG: bool = Field(False)
    OPENAI_MODEL_NAME: str = Field("gpt-4o-mini")
    OPENAI_API_KEY: str = Field("")

    REDIS_URL: str = Field("redis://127.0.0.1:6379")

    # ╦  ┌─┐┌┬┐┌─┐┌┐┌  ╔═╗┌─┐ ┬ ┬┌─┐┌─┐┌─┐┬ ┬┬
    # ║  ├┤ ││││ ││││  ╚═╗│─┼┐│ │├┤ ├┤ ┌─┘└┬┘│
    # ╩═╝└─┘┴ ┴└─┘┘└┘  ╚═╝└─┘└└─┘└─┘└─┘└─┘ ┴ o
    LEMON_STORE_ID: str | None = Field(None)
    LEMON_API_KEY: str = Field("")

    LEMON_STARTER_PLAN_ID: str = Field("")
    LEMON_PRO_PLAN_ID: str = Field("")
    LEMON_FREE_PLAN_ID: str = Field("")

    LIVEKIT_AGENT_NAME: str = "navi-inbound-agent"


# all ways use this settings rather than using __Settings()
settings = __Settings()  # type: ignore

if not mode == "production":
    logger.debug(settings.model_dump_json(indent=3))
