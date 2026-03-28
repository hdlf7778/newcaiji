"""Shared httpx.AsyncClient — single instance reused by all templates"""
import asyncio
import httpx
import config

_client = None
_client_loop_id = None


def get_client() -> httpx.AsyncClient:
    global _client, _client_loop_id
    current_loop_id = id(asyncio.get_event_loop())
    if _client is None or _client.is_closed or _client_loop_id != current_loop_id:
        _client = httpx.AsyncClient(
            headers=config.DEFAULT_HEADERS, verify=False, follow_redirects=True,
            timeout=httpx.Timeout(connect=8, read=15, write=8, pool=20),
        )
        _client_loop_id = current_loop_id
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
