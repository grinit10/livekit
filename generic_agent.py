from typing import Optional
from livekit.agents import function_tool, get_job_context, RunContext, ChatContext
from utils.data_capture import record_data
from base_agent import BaseAgent
from agent_config import config

def make_agent_transition(target_agent_name: str):

    target_node = {}
    for node in config['nodes']:
        if node['name'] == target_agent_name:
            target_node = node
            break
    if not target_node:
        raise ValueError(f"Agent {target_agent_name} not found")
    
    async def transition(context: RunContext):
        return GenericAgent(chat_ctx=context.session._chat_ctx, instructions=target_node['instructions'], name=target_node['name'], \
        data_capture_tools=target_node['data_capture_tools'])
    return transition

class GenericAgent(BaseAgent):
    def __init__(self, chat_ctx: ChatContext, instructions: str, name: str, data_capture_tools: Optional[list] = []):
        tools = []
        edges = [edge for edge in config['edges'] if edge['from'] == name]
        if edges:
            for edge in edges:
                tools.append(function_tool(make_agent_transition(edge['to']), name=edge['name'], description=edge['description']))
        if data_capture_tools:
            for tool in data_capture_tools:
                tools.append(function_tool(record_data(tool['field']), name=tool['name'], description=tool['description']))
        super().__init__(
            instructions=instructions,
            name=name,
            chat_ctx=chat_ctx,
            tools=tools
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply()

    @function_tool()
    async def end_call(self) -> None:
        """Use this tool to indicate that consent has not been given and the call should end or when user wants to end the call."""
        await self.session.say("Thank you for your time, have a wonderful day.")
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))