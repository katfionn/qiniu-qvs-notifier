"""Non-interactive monitoring-service entry point used by ServiceManager."""
import asyncio
from web.monitor import start_daemon

if __name__ == "__main__":
    asyncio.run(start_daemon())
