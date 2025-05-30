from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip, ChatMessage
from livekit.plugins import (
    openai,
    noise_cancellation,
    deepgram,
    silero,
    rime,
)
import json
from livekit.agents import function_tool, get_job_context, RunContext, ChatContext
from dataclasses import dataclass
from livekit.agents.voice.events import ErrorEvent
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from utils.data_capture import record_data
from base_agent import BaseAgent


load_dotenv()


@dataclass
class MySessionInfo:
    date_of_inspection: str | None = None
    time_of_inspection: str | None = None

class HomeValuationAssistant(BaseAgent):
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

    # async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
    #     await self.session.generate_reply()

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


class ConsentCollectorAgent(BaseAgent):
    def __init__(self, chat_ctx: ChatContext):
        super().__init__(
            instructions="""Inform that your name is Lango and you are calling from Language.
            You have the singular task to collect positive consent from the user to record the call. 
            If consent is not given, you must end the call. Unless user specifically says that they do not give their consent, consider that the consent is given. 
            If consent is given, always use on_consent_given tool and otherwise use end_call tool. 
            If user is deviating from the task, redirect him back to the task politely and courteously.
            Invoke the tools only when you get the confirmation from the user that the data you captured is correct.
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

    # async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
    #     await self.session.generate_reply()

    @function_tool()
    async def on_consent_given(self):
        """Use this tool to indicate that consent has been given and the call may proceed."""

        # Perform a handoff, immediately transferring control to the new agent
        return UserDataCollectorAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool to indicate that consent has not been given and the call should end or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))


class UserDataCollectorAgent(BaseAgent):
    def __init__(self, chat_ctx: ChatContext):
        super().__init__(
            instructions="""You work step by step. the steps are as follows and speak in english:
        1. Ask for user's date of inspection and time of inspection.
            1a. If the user provides the information, use the record_date_of_inspection tool.
            1b. If the user does not want to provide the information, use the end_call tool.
        2. Ask for user's time of inspection.
            2a. If the user provides the information, use the record_time_of_inspection tool.
            2b. If the user does not want to provide the information, use the end_call tool.
        3. If user is deviating from the task, redirect him back to the task politely and courteously.
        
        Voice Affect: Calm, composed, and reassuring; project quiet authority and confidence. Make you utterances sound as real as possible.

        Tone: Sincere, empathetic, and gently authoritative—express genuine apology while conveying competence.

        Pacing: Steady and moderate; unhurried enough to communicate care, yet efficient enough to demonstrate professionalism.

        Emotion: Genuine empathy and understanding; speak with warmth, especially during apologies ("I'm very sorry for any disruption...").

        Pronunciation: Clear and precise, emphasizing key reassurances ("smoothly," "quickly," "promptly") to reinforce confidence.

        Pauses: Brief pauses after offering assistance or requesting details, highlighting willingness to listen and support.""",
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    # async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
    #     await self.session.generate_reply()

    @function_tool()
    async def record_date_of_inspection(self, context: RunContext[MySessionInfo], date_of_inspection: str):
        """Use this tool to record the user's date of inspection."""
        await record_data(context, date_of_inspection=date_of_inspection)
    
    @function_tool()
    async def record_time_of_inspection(self, context: RunContext[MySessionInfo], time_of_inspection: str):
        """Use this tool to record the user's time of inspection."""
        await record_data(context, time_of_inspection=time_of_inspection)

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool when both name and email is recorded or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))

async def entrypoint(ctx: agents.JobContext):

    session = AgentSession[MySessionInfo](
        userdata=MySessionInfo(),
        stt=deepgram.STT(model="nova-3", language="multi"),
        tts=rime.TTS(
            model="mist",
            speaker="bayou",
            speed_alpha=0.5,
            reduce_latency=True,
            pause_between_brackets=True,
            api_key="yCjq3alMdqVKAm7P3nbk-upU5V--iuRhL-SZB4tddaE",
        ),
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
        allow_interruptions=True,
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
        agent=ConsentCollectorAgent(chat_ctx=session._chat_ctx),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVCTelephony()
        ),
    )

    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=0.8),
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