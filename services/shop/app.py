"""shop_svc: БД магазина + процесс возврата с ИИ-агентом (защита переносится из прототипа)."""

from fastapi import FastAPI

app = FastAPI(title="shop_svc", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"service": "shop_svc", "status": "ok"}
