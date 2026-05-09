import sys
import asyncio

# Set Windows event loop policy BEFORE anything else
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # Use string import to ensure policy is applied in worker process
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
