"""
main.py

Entry point dell'applicazione FastAPI. Monta i router, configura CORS,
inizializza il database allo startup.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import market, prediction, patterns

app = FastAPI(
    title="Octopus Universal Fractal Prediction API",
    description=(
        "API per l'analisi di Fourier di segmenti frattali selezionati "
        "manualmente dal trader. Non esegue riconoscimento automatico di "
        "pattern: l'identificazione del frattale resta responsabilita' "
        "dell'utente."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(prediction.router)
app.include_router(patterns.router)
app.include_router(patterns.stats_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": settings.environment}
