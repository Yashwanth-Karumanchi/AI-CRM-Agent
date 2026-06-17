import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=10000,
        workers=1,
        loop="asyncio",
        timeout_keep_alive=120,
        log_level="info"
    )