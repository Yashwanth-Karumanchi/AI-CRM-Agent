import uvicorn
from concurrent.futures import ThreadPoolExecutor
import asyncio

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=10000,
        workers=1,
        loop="asyncio",
        timeout_keep_alive=120
    )