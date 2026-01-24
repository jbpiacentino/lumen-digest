import httpx
import os
import re
import logging
import urllib.parse

logger = logging.getLogger(__name__)

# Load configuration
BASE_URL = (os.getenv("FRESHRSS_BASE_URL") or "").rstrip("/")
API_PATH = os.getenv("FRESHRSS_API_PATH", "/api/greader.php")
USERNAME = os.getenv("FRESHRSS_USERNAME", "")
API_PASSWORD = os.getenv("FRESHRSS_API_PASSWORD", "")
VERIFY_SSL = (os.getenv("FRESHRSS_VERIFY_SSL", "true").lower() != "false")

API_ROOT = f"{BASE_URL}{API_PATH}"
DEFAULT_FETCH_LIMIT = int(os.getenv("FRESHRSS_FETCH_LIMIT", "200"))


async def get_auth_token():
    """Step 1: Get the Auth token via ClientLogin"""
    url = f"{API_ROOT}/accounts/ClientLogin"
    params = {"Email": USERNAME, "Passwd": API_PASSWORD}
    
    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        logger.debug(f"Attempting login for {USERNAME} at {url}")
        resp = await client.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            logger.error(f"Login failed: {resp.status_code} - {resp.text}")
            raise Exception(f"FreshRSS Login Failed: {resp.status_code}")

        auth_token = None
        for line in resp.text.splitlines():
            if line.startswith("Auth="):
                auth_token = line.split("=", 1)[1].strip()
                break

        if not auth_token:
            raise RuntimeError("Could not parse Auth token from FreshRSS response")
        
        return auth_token

async def get_edit_token(auth_token: str):
    """Fetch edit token required for tag mutations (FreshRSS/GReader)."""
    url = f"{API_ROOT}/reader/api/0/token"
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}

    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        resp = await client.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            logger.error(f"Edit-token fetch failed: {resp.status_code} - {resp.text}")
            raise Exception(f"FreshRSS Token Error: {resp.status_code}")

        token = resp.text.strip()
        if not token:
            raise RuntimeError("Could not parse edit token from FreshRSS response")

        return token

async def get_unread_entries(limit: int = DEFAULT_FETCH_LIMIT):
    """Step 2: Use the token to fetch articles"""
    auth_token = await get_auth_token()
    
    url = f"{API_ROOT}/reader/api/0/stream/contents/reading-list"
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    params = {
        "output": "json",
        "xt": "user/-/state/com.google/read", # Unread only
        "n": limit,                           # Limit for speed
        "r": "o"                              # Oldest first
    }

    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        logger.debug(f"Fetching unread articles from {url}")
        resp = await client.get(url, headers=headers, params=params, timeout=20)
        
        if resp.status_code != 200:
            logger.error(f"Fetch failed: {resp.status_code}")
            raise Exception(f"FreshRSS Fetch Error: {resp.status_code}")

        data = resp.json()
        items = data.get("items", [])
        logger.info(f"Successfully fetched {len(items)} unread articles.")
        
        return items


async def get_entries_since(
    since_ts: int,
    limit: int = DEFAULT_FETCH_LIMIT,
    max_items: int = 2000,
):
    """Fetch entries from reading-list since an epoch timestamp (seconds)."""
    auth_token = await get_auth_token()

    url = f"{API_ROOT}/reader/api/0/stream/contents/reading-list"
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    params = {
        "output": "json",
        "n": limit,
        "r": "o",
        "ot": int(since_ts),
    }

    items = []
    continuation = None
    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        while True:
            if continuation:
                params["c"] = continuation
            resp = await client.get(url, headers=headers, params=params, timeout=20)
            if resp.status_code != 200:
                logger.error(f"Fetch failed: {resp.status_code}")
                raise Exception(f"FreshRSS Fetch Error: {resp.status_code}")

            data = resp.json()
            batch = data.get("items", []) or []
            if not batch:
                break
            items.extend(batch)
            if len(items) >= max_items:
                items = items[:max_items]
                break
            continuation = data.get("continuation")
            if not continuation:
                break

    logger.info(f"Fetched {len(items)} entries since {since_ts}.")
    return items

async def mark_entries_read(entry_ids):
    """Mark FreshRSS entries as read so they are not re-fetched."""
    if not entry_ids:
        return

    auth_token = await get_auth_token()
    edit_token = await get_edit_token(auth_token)
    url = f"{API_ROOT}/reader/api/0/edit-tag"
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    data = [("i", entry_id) for entry_id in entry_ids]
    data.append(("a", "user/-/state/com.google/read"))
    data.append(("T", edit_token))
    body = urllib.parse.urlencode(data, doseq=True)

    async with httpx.AsyncClient(verify=VERIFY_SSL) as client:
        logger.debug(f"Marking {len(entry_ids)} entries as read via {url}")
        req_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        resp = await client.post(url, headers=req_headers, content=body, timeout=20)

        if resp.status_code != 200:
            logger.error(f"Mark-read failed: {resp.status_code} - {resp.text}")
            raise Exception(f"FreshRSS Mark-Read Error: {resp.status_code}")
