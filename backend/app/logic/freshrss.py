import httpx
import os
import re
import logging

logger = logging.getLogger(__name__)

# Load configuration
BASE_URL = (os.getenv("FRESHRSS_BASE_URL") or "").rstrip("/")
API_PATH = os.getenv("FRESHRSS_API_PATH", "/api/greader.php")
USERNAME = os.getenv("FRESHRSS_USERNAME", "")
API_PASSWORD = os.getenv("FRESHRSS_API_PASSWORD", "")
VERIFY_SSL = (os.getenv("FRESHRSS_VERIFY_SSL", "true").lower() != "false")

API_ROOT = f"{BASE_URL}{API_PATH}"

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

async def get_unread_entries():
    """Step 2: Use the token to fetch articles"""
    auth_token = await get_auth_token()
    
    url = f"{API_ROOT}/reader/api/0/stream/contents/reading-list"
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    params = {
        "output": "json",
        "xt": "user/-/state/com.google/read", # Unread only
        "n": 50                               # Limit for speed
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
