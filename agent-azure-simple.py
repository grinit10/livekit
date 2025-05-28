from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip, ChatMessage
from livekit.agents.utils.audio import audio_frames_from_file
from livekit.plugins import (
    openai,
    noise_cancellation,
    azure,
)
import json
from livekit.agents import function_tool, get_job_context, RunContext, ChatContext
from dataclasses import dataclass
from livekit.agents.voice.events import ErrorEvent

load_dotenv()


@dataclass
class MySessionInfo:
    date_of_inspection: str | None = None
    time_of_inspection: str | None = None


class HomeValuationAssistant(Agent):
    def __init__(self):
        super().__init__(instructions="""You work step by step. the steps are as follows and speak in english:
        1. Introduce yourself and greet the user and ask for consent to record the call.
            1a. If the user gives consent, use the on_consent_given tool.
            1b. If the user does not give consent, use the end_call tool.
        2. Ask the user if he is interested in booking a home valuation inspection.
            2a. If the user is not interested in booking a home valuation inspection, use the end_call tool.
        3. Ask for user's date of inspection and time of inspection.
            3a. If the user provides the information, use the record_date_of_inspection tool.
            3b. If the user does not want to provide the information, use the end_call tool.
        4. Ask for user's time of inspection.
            4a. If the user provides the information, use the record_time_of_inspection tool.
            4b. If the user does not want to provide the information, use the end_call tool.
        5. If user is deviating from the task, redirect him back to the task politely and courteously.
        
        Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence. Make you utterances sound as real as possible.

        Tone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.

        Pacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.

        Emotion: Genuine empathy and understanding; speak with warmth, especially during apologies ("I'm very sorry for any disruption...").

        Pronunciation: Clear and precise, emphasizing key reassurances ("smoothly," "quickly," "promptly") to reinforce confidence.

        Pauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support.""",
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        await self.session.generate_reply()

    @function_tool()
    async def on_consent_given(self, context: RunContext[MySessionInfo]):
        """Use this tool to indicate that consent has been given and the call may proceed."""

        context.userdata.consent = True
        await self.session.generate_reply(Instruction="Ask for user's date of inspection and time of inspection.")

    @function_tool()
    async def record_date_of_inspection(self, context: RunContext[MySessionInfo], date_of_inspection: str):
        """Use this tool to record the user's date of inspection."""
        context.userdata.date_of_inspection = date_of_inspection
        await self.session.generate_reply(Instruction="Ask for user's time of inspection.")

    @function_tool()
    async def record_time_of_inspection(self, context: RunContext[MySessionInfo], time_of_inspection: str):
        """Use this tool to record the user's time of inspection."""
        context.userdata.time_of_inspection = time_of_inspection
        await self.session.generate_reply(Instruction="Thank the user for providing the information and end the call.")

    @function_tool()
    async def end_call(self):
        """Use this tool to indicate that user is not interested in booking a home valuation inspection or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


async def entrypoint(ctx: agents.JobContext):

    tts = azure.TTS(
        speech_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
        speech_endpoint="https://langoedge-ai-dev.cognitiveservices.azure.com/",
    )
    stt = azure.STT(
        speech_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
        speech_endpoint="https://langoedge-ai-dev.cognitiveservices.azure.com/",
    )

    session = AgentSession[MySessionInfo](
        userdata=MySessionInfo(),
        llm=openai.realtime.RealtimeModel.with_azure(
            azure_deployment="gpt-4o-realtime-preview",
            azure_endpoint="https://langoedge-ai-dev.openai.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
            api_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
            api_version="2024-10-01-preview",
            voice="verse",
            input_audio_transcription=None,
        ),
        allow_interruptions=True,
        #llm=openai.realtime.RealtimeModel.with_azure(
        #    azure_deployment="gpt-4o-mini-realtime-preview",
        #    azure_endpoint="https://langoedge-ai-dev.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-mini-realtime-preview",
        #    api_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
        #    api_version="2024-10-01-preview",
        #    voice="coral"
        #),
        tts=tts,
        stt=stt,
    )

    @session.on("error")
    def on_error(ev: ErrorEvent):
        if ev.error.recoverable:
            return

        # To bypass the TTS service in case it's unavailable, we use a custom audio file instead
        session.generate_reply(
            instructions="I'm having trouble connecting right now. Let me transfer your call.",
            allow_interruptions=False,
        )

    await session.start(
        room=ctx.room,
        agent=HomeValuationAssistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVCTelephony()
        ),
    )

    background_audio = BackgroundAudioPlayer(
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=0.7),
        ],
    )


    await ctx.connect()
    dial_info = json.loads(ctx.job.metadata)
    phone_number = dial_info["phone_number"]

    sip_participant_identity = phone_number
    if phone_number is not None:
        # The outbound call will be placed after this method is executed
        try:
            await ctx.api.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                # This ensures the participant joins the correct room
                room_name=ctx.room.name,

                # This is the outbound trunk ID to use (i.e. which phone number the call will come from)
                # You can get this from LiveKit CLI with `lk sip outbound list`
                sip_trunk_id="ST_urFmHaKqX9sz",

                # The outbound phone number to dial and identity to use
                sip_call_to=phone_number,
                participant_identity=sip_participant_identity,

                # This will wait until the call is answered before returning
                wait_until_answered=True,
            ))

            print("call picked up successfully")
        except api.TwirpError as e:
            print(f"error creating SIP participant: {e.message}, "
                  f"SIP status: {e.metadata.get('sip_status_code')} "
                  f"{e.metadata.get('sip_status')}")
            ctx.shutdown()

    else:
        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )
    await background_audio.start(room=ctx.room, agent_session=session)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="my-telephony-agent",
        )
    )