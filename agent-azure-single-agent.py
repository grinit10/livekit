from dotenv import load_dotenv

from livekit import agents, api
from livekit.agents import AgentSession, Agent, RoomInputOptions, BackgroundAudioPlayer, AudioConfig, BuiltinAudioClip, ChatMessage
from livekit.plugins import (
    openai,
    noise_cancellation,
    azure,
)
import json
from livekit.agents import function_tool, get_job_context, RunContext, ChatContext
from dataclasses import dataclass

load_dotenv()


@dataclass
class MySessionInfo:
    user_name: str | None = None
    email: str | None = None


class HelpfulAssistant(Agent):
    def __init__(self, user_name: str | None = None, email: str | None = None):
        super().__init__(instructions="Your only job is to translate what the user is speaking in bengali to english. Be very precise when doing it. Ask for user's feedback\
            Make the conversation interesting and engaging. Ask for feedback from the user and correct urself based on the feedback.")
        self.user_name = user_name
        self.email = email

    async def on_enter(self) -> None:
        self.session.generate_reply()


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
        # llm=openai.realtime.RealtimeModel.with_azure(
        #     azure_deployment="gpt-4o-realtime-preview",
        #     azure_endpoint="https://langoedge-ai-dev.openai.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-realtime-preview",
        #     api_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
        #     api_version="2024-10-01-preview",
        #     voice="coral"
        # ),
        # llm=openai.realtime.RealtimeModel.with_azure(
        #     azure_deployment="gpt-4o-mini-realtime-preview",
        #     azure_endpoint="https://langoedge-ai-dev.cognitiveservices.azure.com/openai/realtime?api-version=2024-10-01-preview&deployment=gpt-4o-mini-realtime-preview",
        #     api_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
        #     api_version="2024-10-01-preview",
        #     voice="coral"
        # ),
        llm=openai.realtime.RealtimeModel.with_azure(
             azure_deployment="gpt-4o-audio-preview",
             azure_endpoint="https://langoedge-ai-dev.cognitiveservices.azure.com/openai/deployments/gpt-4o-audio-preview/chat/completions?api-version=2025-01-01-preview",
             api_key="7WqOeAtLu9brieCVCmaCArSmK2wHCicWH8SsZymx2uy0cWXC7xJVJQQJ99BEACHYHv6XJ3w3AAAAACOGeI1M",
             api_version="2025-01-01-preview",
             voice="coral"
        ),
        tts=tts,
        stt=stt,
    )

    await session.start(
        room=ctx.room,
        agent=HelpfulAssistant(),
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