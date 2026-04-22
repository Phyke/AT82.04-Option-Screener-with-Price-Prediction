from __future__ import annotations

import pickle
from typing import Any

import redis.asyncio as redis_async
from loguru import logger
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import settings

_client: redis_async.Redis | None = None
_connected: bool = False


async def init_cache() -> bool:
    """Connect to Redis. Returns True if connected, False if unavailable.

    Call once at FastAPI startup. Does not raise on connection failure -
    the app will run without caching.
    """
    global _client, _connected
    _client = redis_async.from_url(settings.REDIS_URL, socket_connect_timeout=1.0, socket_timeout=1.0)
    try:
        await _client.ping()
        _connected = True
        logger.info(f"Redis connected at {settings.REDIS_URL}")
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        _connected = False
        logger.warning(f"Redis unavailable, running without cache: {exc}")
    return _connected


async def close_cache() -> None:
    global _client, _connected
    if _client is not None:
        await _client.aclose()
    _client = None
    _connected = False


def is_connected() -> bool:
    return _connected


def _key(name: str) -> str:
    return f"{settings.REDIS_PREFIX}:{name}"


async def get_pickle(name: str) -> Any | None:
    if not _connected or _client is None:
        return None
    try:
        raw = await _client.get(_key(name))
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        logger.warning(f"Redis get failed for {name}: {exc}")
        return None
    if raw is None:
        return None
    try:
        return pickle.loads(raw)
    except Exception as exc:
        logger.warning(f"Redis pickle decode failed for {name}: {exc}")
        return None


async def set_pickle(name: str, value: Any, ttl_seconds: int) -> None:
    if not _connected or _client is None:
        return
    try:
        raw = pickle.dumps(value)
        await _client.set(_key(name), raw, ex=ttl_seconds)
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        logger.warning(f"Redis set failed for {name}: {exc}")


async def delete(name_pattern: str) -> None:
    """Delete all keys matching prefix:pattern."""
    if not _connected or _client is None:
        return
    try:
        cursor = 0
        full_pattern = _key(name_pattern)
        while True:
            cursor, keys = await _client.scan(cursor=cursor, match=full_pattern, count=500)
            if keys:
                await _client.delete(*keys)
            if cursor == 0:
                break
    except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
        logger.warning(f"Redis delete failed for {name_pattern}: {exc}")
