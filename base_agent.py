from dotenv import load_dotenv
import os
from typing import Optional

from livekit.plugins import (
    openai,
    groq,
)
from livekit.agents import (
    Agent,
    llm,
)
from livekit.agents import ChatContext, ChatMessage
import asyncio
from typing import AsyncIterable

load_dotenv()

class BaseAgent(Agent):
    def __init__(self, instructions: str, chat_ctx: ChatContext, id: str, tools: Optional[list] = []):
        super().__init__(
            instructions=instructions,
            llm=openai.LLM.with_azure(
                azure_deployment="gpt-4.1",
                azure_endpoint="https://langoedge-openai-dev.openai.azure.com/", # or AZURE_OPENAI_ENDPOINT
                api_key=os.getenv("AZURE_OPENAI_API_KEY"), # or AZURE_OPENAI_API_KEY
                api_version="2025-01-01-preview", # or OPENAI_API_VERSION
            ),
            tools=tools,
        )
        self.id = id
        self._fast_llm = groq.LLM(
                model="llama-3.1-8b-instant"
            )
        self._fast_llm_prompt = llm.ChatMessage(
            role="system",
            content=[
                "Generate a short instant response to the user's message with 5 to 10 words to make the conversation sound natural and engaging.",
                "Focus on the chat context to generate the response. MUST MAKE SURE THE RESPONSE IS RELEVANT TO THE CHAT CONTEXT IN ENGLISH.",
                "Do not answer the questions directly. Examples:, let me think about that, wait a moment, that's a good question, etc.",
            ],
        )

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage):
        # Create a short "silence filler" response to quickly acknowledge the user's input
        fast_llm_ctx = turn_ctx.copy(
            exclude_instructions=True, exclude_function_call=True
        ).truncate(max_items=3)
        fast_llm_ctx.items.insert(0, self._fast_llm_prompt)
        fast_llm_ctx.items.append(new_message)

        # Intentionally not awaiting SpeechHandle to allow the main response generation to
        # run concurrently
        #self.session.say(
        #    self._fast_llm.chat(chat_ctx=fast_llm_ctx).to_str_iterable(),
        #    add_to_chat_ctx=False,
        #)

        # Alternatively, if you want the reply to be aware of this "silence filler" response,
        # you can await the fast llm done and add the message to the turn context. But note
        # that not all llm supports completing from an existing assistant message.

        fast_llm_fut = asyncio.Future[str]()

        async def _fast_llm_reply() -> AsyncIterable[str]:
            filler_response: str = ""
            async for chunk in self._fast_llm.chat(chat_ctx=fast_llm_ctx).to_str_iterable():
                filler_response += chunk
                yield chunk
            fast_llm_fut.set_result(filler_response)

        await self.session.say(_fast_llm_reply(), add_to_chat_ctx=False)

        filler_response = await fast_llm_fut
        turn_ctx.add_message(role="assistant", content=filler_response, interrupted=False)