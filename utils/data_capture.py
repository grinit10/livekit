from livekit.agents import RunContext

async def record_data(context: RunContext, **kwargs):
    """Use this tool to record user data.
    
    Args:
        **kwargs: Key-value pairs where key is the attribute name and value is the value to set
    """
    for key, value in kwargs.items():
        if hasattr(context.userdata, key):
            setattr(context.userdata, key, value)
    await context.session.generate_reply()