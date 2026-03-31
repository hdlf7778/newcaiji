"""Shared httpx.AsyncClient — single instance reused by all templates"""
import asyncio
import httpx
import config

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    global _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                headers=config.DEFAULT_HEADERS, verify=True, follow_redirects=True,
                timeout=httpx.Timeout(connect=8, read=15, write=8, pool=20),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
