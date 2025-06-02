from dotenv import load_dotenv
from livekit import agents
from livekit.agents import RoomInputOptions, AgentSession, ErrorEvent
from livekit.plugins import elevenlabs, deepgram, silero, noise_cancellation
from generic_agent import GenericAgent
from agent_config import config
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents.voice.events import ErrorEvent
from livekit.agents.voice.background_audio import BackgroundAudioPlayer
from livekit.agents.voice.background_audio import AudioConfig
from livekit.agents.voice.background_audio import BuiltinAudioClip
import json

load_dotenv()


async def entrypoint(ctx: agents.JobContext):

    tts = elevenlabs.TTS(
         voice_id="ODq5zmih8GrVes37Dizd",
         model="eleven_flash_v2_5"
     )
    #tts=rime.TTS(
    #        model="mist",
    #        speaker="bayou",
    #        speed_alpha=0.5,
    #        reduce_latency=True,
    #        pause_between_brackets=True,
    #        api_key="yCjq3alMdqVKAm7P3nbk-upU5V--iuRhL-SZB4tddaE",
    #    )
    session = AgentSession(
        userdata={
            "date_of_inspection": None,
            "time_of_inspection": None,
        },
        stt=deepgram.STT(model="nova-3", language="multi"),
        tts=tts,
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
        agent=GenericAgent(chat_ctx=session._chat_ctx, instructions=config["nodes"][0]["instructions"], \
            name=config["nodes"][0]["name"], data_capture_tools=config["nodes"][0]["data_capture_tools"]),
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