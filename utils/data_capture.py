from livekit.agents import RunContext

def record_data(field: str):
    """Use this tool to record user data.
    
    Args:
        field: The name of the attribute to set
    """
    async def set_value(context: RunContext, value: str):
        if hasattr(context.userdata, field):
            setattr(context.userdata, field, value)
        await context.session.generate_reply()
    return set_value