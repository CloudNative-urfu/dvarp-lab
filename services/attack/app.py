"""attack_svc: симуляция атаки (корпус заморожен, тактика из плана прогона, только текст)."""

from fastapi import FastAPI

app = FastAPI(title="attack_svc", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"service": "attack_svc", "status": "ok"}
