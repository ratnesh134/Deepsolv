import httpx, asyncio, re
from typing import Optional, Tuple
from app.config import settings
from app.exceptions import WebsiteNotFoundError

def _normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url.rstrip("/")

class Fetcher:
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={"User-Agent": settings.USER_AGENT},
            timeout=settings.TIMEOUT_SECS,
            follow_redirects=True
        )

    async def close(self):
        await self.client.aclose()

    async def ensure_root_ok(self, url: str) -> str:
        url = _normalize_url(url)
        try:
            r = await self.client.get(url)
        except httpx.RequestError as e:
            raise WebsiteNotFoundError(str(e))
        if r.status_code >= 400:
            # Per assignment: treat as "website not found"
            raise WebsiteNotFoundError(f"root status {r.status_code}")
        return url

    async def get(self, url: str) -> Optional[httpx.Response]:
        for _ in range(settings.RETRIES + 1):
            try:
                r = await self.client.get(url)
                return r
            except httpx.RequestError:
                continue
        return None

    async def get_text(self, url: str) -> Tuple[int, Optional[str]]:
        r = await self.get(url)
        if not r:
            return (0, None)
        ctype = r.headers.get("content-type", "")
        if "text" in ctype or "json" in ctype:
            return (r.status_code, r.text)
        return (r.status_code, None)
