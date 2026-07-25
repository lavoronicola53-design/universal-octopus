"""
config.py

Configurazione centralizzata via variabili d'ambiente (12-factor app),
con default sicuri per lo sviluppo locale in Docker Compose.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    # --- Database ---
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://pythagoras:pythagoras@db:5432/pythagoras",
    )

    # --- Redis ---
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    # --- Data provider ---
    # "synthetic" (default, nessuna rete richiesta) | "ccxt" (crypto live) | "csv"
    data_provider: str = os.getenv("DATA_PROVIDER", "real")
    ccxt_exchange: str = os.getenv("CCXT_EXCHANGE", "binance")
    ccxt_api_key: str | None = os.getenv("CCXT_API_KEY")
    ccxt_api_secret: str | None = os.getenv("CCXT_API_SECRET")
    csv_paths: dict[str, str] = {}  # popolato eventualmente da un file di config esterno

    # --- CORS ---
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

    # --- App ---
    environment: str = os.getenv("ENVIRONMENT", "development")
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
