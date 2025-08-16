import re
import tldextract
from typing import List
from app.services.fetcher import Fetcher
from app.services.html_utils import soupify

# Simple heuristic using DuckDuckGo HTML (no API key), may be rate-limited in real life.
# Queries: "alternatives to <brand>", "<brand> competitors shopify", "site:myshopify.com <category>"
DUCK_URL = "https://duckduckgo.com/html/?q="

def _domain(url: str) -> str:
    ext = tldextract.extract(url)
    return ".".join(x for x in [ext.domain, ext.suffix] if x)

async def discover_competitors(fetcher: Fetcher, base_url: str, brand_name: str | None, n: int = 3) -> List[str]:
    q = f"{brand_name or _domain(base_url)} competitors shopify"
    url = DUCK_URL + q.replace(" ", "+")
    status, html = await fetcher.get_text(url)
    if not html or status >= 400:
        return []
    soup = soupify(html)
    results = []
    for a in soup.select("a.result__a, a[href]"):
        href = a.get("href", "")
        if "http" in href and "duckduckgo.com" not in href:
            # crude filter: prefer shopify-powered domains
            if re.search(r"(myshopify|/products/|/collections/|/pages/)", href):
                results.append(href.split("&")[0])
        if len(results) >= n * 2:
            break
    # Normalize to unique brand base domains
    uniq = []
    seen = set()
    for r in results:
        d = _domain(r)
        if d and d not in seen and d != _domain(base_url):
            uniq.append("https://" + d)
            seen.add(d)
        if len(uniq) >= n:
            break
    return uniq
