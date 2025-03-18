import os
from typing import Any, TypedDict

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    llm,
    metrics,
    stt,
    tts,
)
from livekit.agents.pipeline import AgentTranscriptionOptions, VoicePipelineAgent
from livekit.plugins import (
    google,
    silero,
    turn_detector,
)
from loguru import logger

from app.agent.schema import AgentSettings
from com_bridge.dialer import voicecab_dailer
from com_bridge.schemas import AgentLookupInputs

credentials_file = "credentials.json"


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

    if agent_settings.synth_provider == "google":
        tts = google.TTS(
            voice_name=agent_settings.voices[0]["voice_id"],
            credentials_file=credentials_file,
        )
    else:
        raise ValueError(
            f"Synth provider {agent_settings.synth_provider} not yet implemented"
        )

    if agent_settings.model_provider == "google":
        llm = google.LLM(api_key=os.environ["GOOGLE_API_KEY"], temperature=0.9)
    else:
        raise ValueError(
            f"STT provider {agent_settings.model_provider} not yet implemented"
        )

    if agent_settings.transiber_provider == "google":
        stt = google.STT(credentials_file=credentials_file)
    else:
        raise ValueError(
            f"STT provider {agent_settings.transiber_provider} not yet implemented"
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
        logger.debug(f"\n Room Metadata:\n {ctx.room.metadata}")
        logger.info(f"connecting to room {ctx.room.name}")
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

        # Wait for the first agent participant to connect
        participant = await ctx.wait_for_participant()
        agent_attributes = participant.attributes or {}

        logger.info(f"starting voice assistant for participant {participant.identity}")
        logger.info(f"Attributes: {agent_attributes}")

        agent_phone = agent_attributes.get(
            "sip.trunkPhoneNumber", agent_attributes.get("agent_phone", None)
        )

        customer_phone = agent_attributes.get(
            "sip.phoneNumber", agent_attributes.get("customer_phone", None)
        )

        if agent_phone is None or customer_phone is None:
            logger.error(
                "Both agent_phone and customer_phone are required, if you are using websocket make sure you pass a dummy number to the agent participant so shutting down room..."
            )
            ctx.shutdown()
            return

        # Get the agent settings from API call
        agent_settings = await voicecab_dailer.lookup_agent_with(
            inputs=AgentLookupInputs(
                phone_number=agent_phone,
                customer_phone=customer_phone,
            )
        )
        if not agent_settings:
            logger.error("Could not get agent settings, shutting down room...")
            ctx.shutdown()
            return

        # build the full prompt including date/time and additional intructions
        full_prompt = agent_settings.build_prompt(include_greeting=False)

        logger.debug(
            f"\n\nFull Adjusted Prompt: \n{'---' * 20} \n {full_prompt} \n {'---' * 20}\n\n"
        )
        initial_ctx = llm.ChatContext().append(
            role="system",
            text=full_prompt,
        )

        vp_cfg = get_pipeline_agent_settings(agent_settings=agent_settings)

        # Initialize the agent
        agent = VoicePipelineAgent(
            vad=ctx.proc.userdata["vad"],
            stt=vp_cfg["stt"],
            llm=vp_cfg["llm"],
            tts=vp_cfg["tts"],
            turn_detector=turn_detector.EOUModel(),
            allow_interruptions=True,
            transcription=AgentTranscriptionOptions(),
            chat_ctx=initial_ctx,
            plotting=True,
        )

        usage_collector = metrics.UsageCollector()

        @agent.on("metrics_collected")
        def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
            metrics.log_metrics(agent_metrics)
            usage_collector.collect(agent_metrics)

        agent.start(ctx.room, participant)

        # speak greeting message
        await agent.say(
            source=agent_settings.greeting_message,
            allow_interruptions=True,
        )
