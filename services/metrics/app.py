"""metrics_svc: расчёт метрик (L* и формулы канона) поверх сырой БД — в любое время."""

from fastapi import FastAPI

app = FastAPI(title="metrics_svc", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"service": "metrics_svc", "status": "ok"}
