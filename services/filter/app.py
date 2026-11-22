"""filter_svc: разделение ответа и сырых данных; сырьё + снимки в свою БД (хеш-цепочка)."""

from fastapi import FastAPI

app = FastAPI(title="filter_svc", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"service": "filter_svc", "status": "ok"}
