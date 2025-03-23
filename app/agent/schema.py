from datetime import datetime
import os
from typing import Literal
from pydantic import BaseModel, Field, computed_field
from loguru import logger

from app.agent.tools import ToolConfig


AgentVoiceProvider = Literal["openai", "google"]
AgentLLMProvider = Literal["openai", "google"]
AgentTranscriberProvider = Literal["deepgram", "google", "openai"]


class MakeOutboundCallInputs(BaseModel):
    from_number: str | None = None
    to_number: str


class AgentSecretSettings(BaseModel):
    open_api_key: str | None = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )


class AgentVoice(BaseModel):
    voice_name: str
    language_code: str
    model: str | None = None


class AgentSynthSettings(BaseModel):
    synth_provider: AgentVoiceProvider = "openai"
    language_code: str = "en"
    voice: AgentVoice = AgentVoice(voice_name="alloy", language_code="en")


class AgentTranscriberSettings(BaseModel):
    transcriber_provider: AgentTranscriberProvider = "deepgram"


class AgentLLMProviderSettings(BaseModel):
    model_provider: AgentLLMProvider = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7


class CustomerInfo(BaseModel):
    customer_name: str | None = "N/A"
    customer_email: str | None = "N/A"
    customer_phone: str | None = "N/A"
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}


class ToolsInfo(BaseModel):
    knowledgebase_ids: list[str] = []
    actions: list[ToolConfig] = []


class AgentClientInformation(BaseModel):
    account_id: str | None = None
    """ the account id of the user that is using this agent """


class AgentSettings(
    AgentClientInformation,
    AgentSynthSettings,
    AgentTranscriberSettings,
    AgentLLMProviderSettings,
    AgentSecretSettings,
    # CustomerInfo,
    ToolsInfo,
):
    greeting_message: str
    system_prompt: str
    agent_name: str = "Navi"
    agent_phone: str | None = Field(
        default_factory=lambda: os.getenv("TEST_AGENT_PHONE")
    )
    agent_id: str | None = None
    interaction_id: str | None = None

    @computed_field
    @property
    def language_name(self) -> str:
        mappings = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
        }
        try:
            part = self.language_code.split("-")[0].lower()
            return mappings[part]
        except KeyError:
            logger.error(
                f"Language code {self.language_code} not found in mappings, using default: English"
            )
            return "English"

    def build_prompt(self, include_greeting: bool = True) -> str:
        now = datetime.now()
        prompt = f"{self.system_prompt}"

        if include_greeting:
            prompt += f"\nbegin by greeting the customer with the greeting message {self.greeting_message}"

        prompt += "[Additional Instructions]: \n Remember that you're on a phone call, and your response will be converted to audio. Avoid producing lists and special characters like asterisks (*).\n"

        prompt += f"""
The call is starting at: {now.strftime("%Y-%m-%d %H:%M:%S")}.
Avoid producing time and date information in numerical formats like "9:00 AM" or "23:25." Instead, provide them in natural language
such as "nine o’clock," "today," or "six forty-five in the morning. 
When mentioning email addresses, spell them out clearly. For example, "john.doe@example.com" should be pronounced as "john dot doe at example dot com. 
"""

        if self.language_code is not None:
            prompt += f"Always speak in {self.language_name} even if the user speaks in another language or wants to use another language.\n"

        # if self.customer_email or self.customer_email or self.customer_phone:
        #     prompt += f"\n {'--' * 10} \n\n ## [Customer Information]:  \n Customer name: {self.customer_name} \n Customer email: {self.customer_email} \n Customer phone: {self.customer_phone}\n\n - Never ask of customer details since you already know them, but always ask for confirmation"

        return prompt
