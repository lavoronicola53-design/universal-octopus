"""
database.py

Setup SQLAlchemy: engine, session factory, base dichiarativa e
dependency FastAPI per ottenere una sessione per-request.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """Dependency FastAPI: fornisce una sessione DB e la chiude sempre,
    anche in caso di eccezione."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea tutte le tabelle mappate su Base se non esistono gia'.
    In produzione si consiglia di sostituire con Alembic per le
    migrazioni versionate; qui teniamo lo startup semplice."""
    from . import models  # noqa: F401  (registra i modelli su Base.metadata)
    Base.metadata.create_all(bind=engine)
