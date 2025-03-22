from livekit import rtc, api
from livekit.agents import llm, JobContext
from typing import Annotated
from datetime import datetime
import aiohttp
from loguru import logger
from pydantic import BaseModel


class ToolInput(BaseModel):
    required: bool = False
    description: str


class ToolConfig(BaseModel):
    name: str
    description: str

    # Inputs are formatted into body (POST) or query params (GET)
    properties: dict[str, ToolInput] = {}

    # URL config
    url_template: str
    method: str = "GET"
    headers: dict[str, str] = dict()


def create_dynamic_function(config: ToolConfig):
    """Creates a dynamic async function based on ToolConfig"""

    params = []
    for prop_name, prop_schema in config.properties.items():
        params.append(f"{prop_name}: str")

    func_def = f"""
async def dynamic_function(self, {", ".join(params)}):
    if webhook_url:
        async with aiohttp.ClientSession() as session:
            data = {{
                {", ".join(f'"{param.split(":")[0]}": {param.split(":")[0]}' for param in params)}
            }}
            logger.info(f"Function inputs: {{data}}")
            logger.info(f"Function method: {{config.method}}")

            parsed_url = webhook_url.format(**data)
            try:
                async with session.request(method=config.method, url=parsed_url, json=data, headers=config.headers) as response:
                    response.raise_for_status()
                    data = await response.json()
            except Exception as e:
                logger.error(f"Error calling webhook: {{e}}")
                return {{"error": str(e)}}

            logger.info(f"Function response: {{data}}")
            return data
        """

    # Create function namespace
    namespace = {
        "aiohttp": aiohttp,
        "logger": logger,
        "webhook_url": config.url_template,
        "config": config,
    }
    exec(func_def, namespace)
    dynamic_function = namespace["dynamic_function"]

    dynamic_function.__name__ = config.name  # type: ignore
    dynamic_function.__doc__ = config.description

    # Add type hints after function creation
    annotations = {}
    for prop_name, prop_schema in config.properties.items():
        annotations[prop_name] = Annotated[str, prop_schema.description]
    dynamic_function.__annotations__ = annotations

    return dynamic_function


class CallActions(llm.FunctionContext):
    """
    AI function calls for handling outbound calls.
    """

    def __init__(
        self,
        *,
        api: api.LiveKitAPI,
        participant: rtc.RemoteParticipant,
        room: rtc.Room,
        ctx: JobContext,
    ):
        super().__init__()
        self.api = api
        self.participant = participant
        self.room = room
        self.ctx = ctx

    async def hangup(self):
        """Ends the call."""
        try:
            await self.api.room.remove_participant(
                api.RoomParticipantIdentity(
                    room=self.room.name, identity=self.participant.identity
                )
            )
            await self.api.room.delete_room(api.DeleteRoomRequest(room=self.room.name))
            self.ctx.shutdown()

        except Exception as e:
            logger.info(f"Error while ending call: {e}")

    async def end_call(self):
        """Use this when you or the user says goodbye and want to end the call."""
        logger.info(f"Ending call for {self.participant.identity}")
        await self.hangup()

    async def detected_answering_machine(
        self, reason: Annotated[str, "Reason of detecting answering machine"]
    ):
        """Ends call if it reaches voicemail."""
        logger.info(
            f"Detected answering machine for {self.participant.identity}, {reason}"
        )
        await self.hangup()

    @llm.ai_callable()
    async def get_time(self):
        """Called to retrieve the current local time"""
        return datetime.now().strftime("%H:%M:%S")


def create_call_actions_class(
    enabled_functions: list, dynamic_schemas: list[ToolConfig] = []
):
    """
    Creates a subclass of CallActions with enabled functions and dynamic functions.
    Args:
        enabled_functions: List of predefined function names to enable
        dynamic_schemas: Dict of {function_name: schema_dict} for dynamic functions
    """

    class DynamicCallActions(CallActions):
        pass

    # Enable predefined functions
    for func_name in enabled_functions:
        if hasattr(DynamicCallActions, func_name):
            func = getattr(DynamicCallActions, func_name)
            decorated_func = llm.ai_callable()(func)
            setattr(DynamicCallActions, func_name, decorated_func)

    # Create and add dynamic functions
    for tool in dynamic_schemas:
        dynamic_func = create_dynamic_function(tool)
        decorated_func = llm.ai_callable(name=tool.name, description=tool.description)(
            dynamic_func
        )
        setattr(DynamicCallActions, tool.name, decorated_func)

    return DynamicCallActions


enabled_functions = ["end_call", "look_up_availability", "detected_answering_machine"]


tools = [
    ToolConfig.model_validate(
        {
            "name": "book_taxi",
            "description": "Book a taxi.",
            "url_template": "https://webhook.site/b54691fd-e7bb-4a26-a5be-aee1e3017c39/book-taxi?pick_up_location={pick_up_location}&drop_off_location={drop_off_location}",
            "method": "POST",
            "properties": {
                "pick_up_location": {
                    "description": "Pick-up location for the taxi",
                    "required": True,
                },
                "drop_off_location": {
                    "description": "Drop-off location for the taxi",
                    "required": True,
                },
            },
        }
    ),
    ToolConfig(
        name="book_appointment",
        description="Book an appointment slot for a patient.",
        url_template="https://webhook.site/b54691fd-e7bb-4a26-a5be-aee1e3017c39/book-appointment",
        method="POST",
        properties={
            "slot_id": ToolInput(
                description="The ID of the appointment slot to book", required=True
            ),
            "patient_name": ToolInput(description="Name of the patient", required=True),
        },
    ),
    ToolConfig(
        name="get_weather",
        description="Fetches weather data for a given city.",
        url_template="https://webhook.site/b54691fd-e7bb-4a26-a5be-aee1e3017c39/weather?city={city}",
        method="GET",
        headers={"Content-Type": "application/json", "x-api-key": "xxxxx"},
        properties={
            "city": ToolInput(
                description="The city name to fetch weather for", required=True
            ),
        },
    ),
    ToolConfig(
        name="submit_ticket",
        description="Submit a customer support ticket.",
        url_template="https://webhook.site/b54691fd-e7bb-4a26-a5be-aee1e3017c39/support-ticket",
        method="POST",
        properties={
            "customer_name": ToolInput(
                description="Customer's full name", required=True
            ),
            "email": ToolInput(description="Customer's email address", required=True),
            "issue_description": ToolInput(
                description="Detailed description of the issue", required=True
            ),
        },
    ),
]


# Create call actions with both predefined and dynamic functions
DynamicCallActionsCls = create_call_actions_class(
    enabled_functions=enabled_functions, dynamic_schemas=tools
)

if __name__ == "__main__":
    action = DynamicCallActionsCls(api=None, participant=None, room=None, ctx=None)  # type: ignore
    print(action)
