from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, get_job_context
from livekit.plugins import (
    openai,
    noise_cancellation,
    cartesia,
    silero,
)
import json
from livekit.agents import function_tool
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()


class HelpfulAssistant(Agent):
    def __init__(self):
        super().__init__(instructions="You are a helpful voice AI assistant.")

    async def on_enter(self) -> None:
        await self.session.say("Hello, how can I help you today?")


class ConsentCollectorAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""Your are a voice AI agent with the singular task to collect positive 
            recording consent from the user. If consent is not given, you must end the call."""
        )

    async def on_enter(self) -> None:
        await self.session.say("May I record this call for quality assurance purposes?")

    @function_tool()
    async def on_consent_given(self):
        """Use this tool to indicate that consent has been given and the call may proceed."""

        # Perform a handoff, immediately transfering control to the new agent
        return HelpfulAssistant()

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool to indicate that consent has not been given and the call should end."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))

async def entrypoint(ctx: agents.JobContext):
    
    session = AgentSession(
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        stt=openai.STT(
            model="gpt-4o-transcribe",
        ),
        vad=silero.VAD.load(),
        turn_detector=MultilingualModel()
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
                sip_trunk_id='ST_Uj5bYGtz5kUq',

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


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="my-telephony-agent",
        )
    )