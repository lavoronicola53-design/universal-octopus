"""
cache.py

Wrapper minimale su Redis per caching dei risultati (richiesto dalle
specifiche: "Caching: Redis"). Usato principalmente per:
- risposte OHLCV storiche gia' calcolate/recuperate di recente
- risultati di previsione per combinazioni (market, timeframe, selezione,
  parametri) identiche, cosi' da rispettare piu' facilmente il target di
  performance in caso di richieste ripetute

Il fallback e' "no-op" se Redis non e' raggiungibile (es. ambiente di
sviluppo senza il container redis attivo), per non bloccare l'app.
"""
from __future__ import annotations

import json
import hashlib
from typing import Any, Optional

from .config import settings

try:
    import redis  # type: ignore
    _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
except Exception:  # pragma: no cover
    _client = None


def _safe_call(fn, *args, **kwargs):
    if _client is None:
        return None
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def make_key(prefix: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{prefix}:{digest}"


def get_json(key: str) -> Optional[Any]:
    raw = _safe_call(_client.get, key) if _client else None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    if _client is None:
        return
    ttl = ttl if ttl is not None else settings.cache_ttl_seconds
    _safe_call(_client.set, key, json.dumps(value), ex=ttl)
