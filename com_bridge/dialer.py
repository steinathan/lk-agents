import os
from dotenv import load_dotenv
import httpx
from loguru import logger

from app.agent.schema import AgentSettings
from com_bridge.schemas import AgentLookupInputs, CustomerInfo
from mock_db.mock_agent_data import find_test_agent
from utils.singleton import Singleton

load_dotenv(dotenv_path=".env.local")


class VoiceCabDialer(Singleton):
    def __init__(self):
        self.test_mode = os.getenv("VOICECAB_API_TEST_MODE", False)
        self.BASE_URL = os.environ["VOICECAB_API_URL"]
        self.client = httpx.AsyncClient(base_url=self.BASE_URL)
        self.ping()

    def ping(self):
        logger.info("Pinging VoiceCab API, making sure it's healthy...")
        if self.test_mode:
            return

        try:
            with httpx.Client(base_url=self.BASE_URL) as client:
                res = client.get("/health")
                res.raise_for_status()
                logger.info("VoiceCab API is healthy")
        except Exception:
            logger.error(
                "VoiceCab API is not healthy, subsequent calls will fail, server will not startup!"
            )
            raise

    async def lookup_customer(self, phone_number: str) -> CustomerInfo | None:
        logger.info(f"Looking up customer with phone number: {phone_number}")
        try:
            response = await self.client.get(f"/customers/{phone_number}")
            response.raise_for_status()
            return CustomerInfo.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to lookup customer: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during customer lookup: {e}")
        return None

    async def lookup_agent_with(
        self, inputs: AgentLookupInputs
    ) -> AgentSettings | None:
        logger.info(
            f"Looking up agent with criteria: {inputs} in test mode: {self.test_mode}"
        )

        if self.test_mode:
            return await self._test_lookup_agent_with(inputs)

        try:
            response = await self.client.post("/agents/lookup", json=inputs.__dict__)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to lookup agent: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Network error during agent lookup: {e}")
        return None

    async def _test_lookup_agent_with(self, inputs: AgentLookupInputs):
        logger.info(f"Looking up agent on TEST_MODE with criteria: {inputs}")
        return await find_test_agent(
            phone_number=inputs.phone_number,
            agent_id=inputs.agent_id,
            interaction_id=inputs.interaction_id,
        )

    async def close(self):
        await self.client.aclose()


voicecab_dailer = VoiceCabDialer()
