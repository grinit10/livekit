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
from utils.immediate_feedback import immediate_feedback
from livekit.agents.voice.events import ErrorEvent

load_dotenv()


@dataclass
class MySessionInfo:
    user_name: str | None = None
    email: str | None = None


class HomeValuationAssistant(Agent):
    def __init__(self, chat_ctx: ChatContext):
        super().__init__(instructions="""Your only job is to get user to book a home valuation inspection. If user is not interested in booking, end the call.\
        Focus on getting the user to book a home valuation inspection. Inform the user that the service is free and it will help him know how the property market is doing.\
        Please speak in english. Make your tone engaging and friendly.\
        Invoke the tools only when you get the confirmation from the user that the data you captured is correct.\
        FInally, if you face technical connectivity issues, inform the user that you are trying to recover from a technical issue.
        
        Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence.

        Tone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.

        Pacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.

        Emotion: Genuine empathy and understanding; speak with warmth, especially during apologies ("I'm very sorry for any disruption...").

        Pronunciation: Clear and precise, emphasizing key reassurances ("smoothly," "quickly," "promptly") to reinforce confidence.

        Pauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support.""",
        chat_ctx=chat_ctx)

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        await self.session.generate_reply()

    @function_tool()
    async def on_positive_response(self):
        """Use this tool when user is interested in booking a home valuation inspection."""

        # Perform a handoff, immediately transferring control to the new agent
        return UserDataCollectorAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def end_call(self):
        """Use this tool to indicate that user is not interested in booking a home valuation inspection or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


class ConsentCollectorAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are a voice AI agent with the singular task to collect positive 
            consent from the user to record the call. If consent is not given, you must end the call. 
            If consent is given, always use on_consent_given tool and otherwise use end_call tool.
            If user is deviating from the task, redirect him back to the task politely and courteously.
            Invoke the tools only when you get the confirmation from the user that the data you captured is correct.
            Please speak in english. Make your tone engaging and friendly.
            FInally, if you face technical connectivity issues, inform the user that you are trying to recover from a technical issue.
            
            Tone:
            Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence.

            Tone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.

            Pacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.

            Emotion: Genuine empathy and understanding; speak with warmth, especially during apologies ("I'm very sorry for any disruption...").

            Pronunciation: Clear and precise, emphasizing key reassurances ("smoothly," "quickly," "promptly") to reinforce confidence.

            Pauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support."""
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        await self.session.generate_reply()

    @function_tool()
    async def on_consent_given(self):
        """Use this tool to indicate that consent has been given and the call may proceed."""

        # Perform a handoff, immediately transferring control to the new agent
        return HomeValuationAssistant(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool to indicate that consent has not been given and the call should end or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


class UserDataCollectorAgent(Agent):
    def __init__(self, chat_ctx: ChatContext):
        super().__init__(
            instructions="""Your are a voice AI agent with the singular task to collect the user's name and email address. Ask user to spell his name and email address.
            Ask for one at a time. Always use the record_name tool to record the user's name and the record_email tool to record the user's email address.
            Once a user has provided his input, repeat it back to him to confirm the details are captured correctly.
            Invoke the tools only when you get the confirmation from the user that the data you captured is correct.
            Please speak in english. Proactively ask for user's name and email address. If user has already provided his name, do not ask for it again. Make your tone engaging and friendly.
            FInally, if you face technical connectivity issues, inform the user that you are trying to recover from a technical issue.
            
            Tone:
            Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence.

            Tone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.

            Pacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.

            Emotion: Genuine empathy and understanding; speak with warmth, especially during apologies ("I'm very sorry for any disruption...").

            Pronunciation: Clear and precise, emphasizing key reassurances ("smoothly," "quickly," "promptly") to reinforce confidence.

            Pauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support.""",
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        await self.session.generate_reply()

    @function_tool()
    async def record_name(self, context: RunContext[MySessionInfo], name: str):
        """Use this tool to record the user's name."""
        context.userdata.user_name = name
        await self.session.generate_reply()
    
    @function_tool()
    async def record_email(self, context: RunContext[MySessionInfo], email: str):
        """Use this tool to record the user's email address."""
        context.userdata.email = email
        await self.session.generate_reply()

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool when both name and email is recorded or when user wants to end the call."""
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
            voice="coral",
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
        agent=ConsentCollectorAgent(),
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