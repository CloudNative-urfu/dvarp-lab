"""traffic_svc: симуляция безопасного трафика (стили общения, правдивые возвраты из БД)."""

from fastapi import FastAPI

app = FastAPI(title="traffic_svc", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"service": "traffic_svc", "status": "ok"}
