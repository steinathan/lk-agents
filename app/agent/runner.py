import json
from json import tool
import os
from typing import Any, TypedDict

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    llm,
    metrics,
    stt,
    multimodal,
    tts,
)
from livekit.plugins import (
    google,
    silero,
)
from loguru import logger
from livekit.agents.pipeline import VoicePipelineAgent

from app.agent.schema import AgentSettings
from app.agent.service import AssistantService
from livekit import api

# from app.agent.tools import create_assistant_tool
from app.core.database import get_session_db
from livekit.agents.pipeline import AgentTranscriptionOptions
import app.agent.tools as tools


from livekit.plugins import deepgram, openai

credentials_file = "credentials.json"


IS_MULTI_MODAL = False


class VoicePipelineAgentSettings(TypedDict):
    stt: stt.STT
    llm: llm.LLM
    tts: tts.TTS


def get_pipeline_agent_settings(
    agent_settings: AgentSettings,
) -> VoicePipelineAgentSettings:
    """Get the pipeline agent settings, works for google for now"""
    stt: Any = None
    llm: Any = None
    tts: Any = None

    # TTS
    if agent_settings.synth_provider == "google":
        tts = google.TTS(
            voice_name=agent_settings.voice.voice_name,
            credentials_file=credentials_file,
        )

    elif agent_settings.synth_provider == "openai":
        tts = openai.TTS(
            api_key=agent_settings.open_api_key,
            voice=agent_settings.voice.voice_name,
            model=agent_settings.voice.model or "tts-1",
        )
    else:
        raise ValueError(
            f"Synth provider {agent_settings.synth_provider} not yet implemented"
        )

    # LLM
    if agent_settings.model_provider == "google":
        llm = google.LLM(api_key=os.environ["GOOGLE_API_KEY"], temperature=0.9)
    elif agent_settings.model_provider == "openai":
        llm = openai.LLM(
            model="gpt-4o-mini",
        )
        if False:
            llm = AssistantLLM(
                api_key=agent_settings.open_api_key,
                assistant_opts=AssistantOptions(
                    create_options=AssistantCreateOptions(
                        model=typing.cast(ChatModels, agent_settings.model),
                        instructions=agent_settings.build_prompt(),
                        name=f"Assistant {agent_settings.agent_name}",
                        temperature=agent_settings.temperature,
                    )
                ),
            )
    else:
        raise ValueError(
            f"STT provider {agent_settings.model_provider} not yet implemented"
        )

    # STT
    if agent_settings.transcriber_provider == "google":
        stt = google.STT(credentials_file=credentials_file)
    elif agent_settings.transcriber_provider == "deepgram":
        stt = deepgram.STT(
            api_key=os.environ["DEEPGRAM_API_KEY"], language="en-US", model="nova-3"
        )
    elif agent_settings.transcriber_provider == "openai":
        stt = openai.STT(api_key=agent_settings.open_api_key)
    else:
        raise ValueError(
            f"STT provider {agent_settings.transcriber_provider} not yet implemented"
        )

    return {
        "llm": llm,
        "stt": stt,
        "tts": tts,
    }


class VoiceAgent:
    @staticmethod
    def prewarm(proc: JobProcess):
        proc.userdata["vad"] = silero.VAD.load()

    @staticmethod
    async def entrypoint(ctx: JobContext):
        service = AssistantService(next(get_session_db()))

        logger.debug(f"\n Room Metadata:\n {ctx.room.metadata}")
        logger.info(f"connecting to room {ctx.room.name}")
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

        metadict = json.loads(ctx.job.metadata or ctx.room.metadata or "{}")

        # `create_sip_participant` starts dialing the user
        if (
            metadict.get("direction", None) == "outbound"
            and metadict.get("sip_trunk_id", None) is not None
            and metadict.get("customer_phone", None) is not None
        ):
            logger.info(f"starting outbound call: {metadict}")
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=metadict["sip_trunk_id"],
                    sip_call_to=metadict["customer_phone"],
                    participant_identity=metadict.get(
                        "agent_name", "Default Agent Name"
                    ),
                    wait_until_answered=True,
                )
            )

        # Wait for the first agent participant to connect
        participant = await ctx.wait_for_participant()

        agent_attributes = participant.attributes or {}

        logger.info(f"starting voice assistant for participant {participant.identity}")

        agent_phone = agent_attributes.get(
            "sip.trunkPhoneNumber",
            agent_attributes.get("agent_phone", metadict.get("agent_phone", None)),
        )

        customer_phone = agent_attributes.get(
            "sip.phoneNumber",
            agent_attributes.get(
                "customer_phone", metadict.get("customer_phone", None)
            ),
        )

        logger.info(
            f"info: agent phone: {agent_phone}, customer phone: {customer_phone}"
        )

        if agent_phone is None or customer_phone is None:
            logger.error(
                "Both agent_phone and customer_phone are required, if you are using websocket make sure you pass a dummy number to the agent participant so shutting down room..."
            )
            ctx.shutdown()
            return

        agent = await service.find_agent_by(
            phone_number=agent_phone,
        )

        if not agent:
            logger.error("Could not find agent, shutting down room...")
            ctx.shutdown()
            return

        agent_settings = AgentSettings.model_validate(agent.config)

        # build the full prompt including date/time and additional intructions
        full_prompt = agent_settings.build_prompt(include_greeting=False)

        logger.debug(
            f"\n\nFull Adjusted Prompt: \n{'---' * 20} \n {full_prompt} \n {'---' * 20}\n\n"
        )

        # Add the prompt to the context
        initial_ctx = llm.ChatContext().append(
            role="system",
            text=full_prompt,
        )

        voice_pipeline_config = get_pipeline_agent_settings(
            agent_settings=agent_settings
        )

        # initialize the agent
        enabled_functions = [
            "end_call",
            "detected_answering_machine",
        ]

        logger.info(f"created {len(agent_settings.actions)} dynamic functions")
        DynamicCallActionsCls = tools.create_call_actions_class(
            enabled_functions=enabled_functions, dynamic_schemas=agent_settings.actions
        )
        fnc_ctx = DynamicCallActionsCls(
            api=ctx.api,
            participant=participant,
            room=ctx.room,
            ctx=ctx,
        )

        if IS_MULTI_MODAL:
            agent = multimodal.MultimodalAgent(
                model=openai.realtime.RealtimeModel(
                    voice="alloy",
                    temperature=0.8,
                    instructions=(
                        "You are a helpful assistant, greet the user and help them with their trip planning. "
                        "When performing function calls, let user know that you are checking the weather."
                    ),
                    turn_detection=openai.realtime.ServerVadOptions(
                        threshold=0.6, prefix_padding_ms=200, silence_duration_ms=500
                    ),
                ),  # type: ignore
                fnc_ctx=fnc_ctx,
                chat_ctx=initial_ctx,
            )
        else:
            agent = VoicePipelineAgent(
                vad=ctx.proc.userdata["vad"],
                stt=voice_pipeline_config["stt"],
                llm=voice_pipeline_config["llm"],
                tts=voice_pipeline_config["tts"],
                allow_interruptions=True,
                transcription=AgentTranscriptionOptions(),
                chat_ctx=initial_ctx,
                fnc_ctx=fnc_ctx,
            )

        usage_collector = metrics.UsageCollector()

        @agent.on("metrics_collected")
        def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
            metrics.log_metrics(agent_metrics)
            usage_collector.collect(agent_metrics)

        agent.start(ctx.room, participant)

        if isinstance(agent, multimodal.MultimodalAgent):
            agent.generate_reply()
        else:
            await agent.say(
                source=agent_settings.greeting_message,
                allow_interruptions=True,
            )
