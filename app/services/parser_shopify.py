# app/services/parser_shopify.py
import json
import re
import asyncio
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup

from app.services.fetcher import Fetcher
from app.services.html_utils import (
    soupify,
    find_links,
    absolutize,
    extract_emails_phones,
    extract_socials,
    extract_jsonld_faqs,
    extract_brand_name,
)
from app.services.normalizer import clean_text, unique_keep_order
from app.services.llm_groq import call_groq_llm, GroqLLMError
from app.config import settings
from app.models.schemas import (
    Product,
    Policy,
    FAQItem,
    SocialHandles,
    ContactInfo,
    ImportantLinks,
    BrandContext,
)
from app.exceptions import ParsingError

# Constants / heuristics (kept for pre-fetching and link discovery)
COMMON_POLICY_ROUTES = [
    "/policies/privacy-policy",
    "/policies/refund-policy",
    "/policies/shipping-policy",
]

FAQ_HINTS = ["faq", "faqs", "help", "support"]
ABOUT_HINTS = ["about", "our story", "about us", "about-us"]
TRACK_HINTS = ["track", "order tracking", "track order", "track-order"]
BLOG_HINTS = ["blog", "blogs", "journal"]
CONTACT_HINTS = ["contact", "contact us", "support", "customer service"]

PRODUCT_LINK_PAT = re.compile(r"/products/[^/]+/?$", re.I)
PHONE_STRICT = re.compile(r"^\+\d{1,3}-\d{7,15}$")  # final strict pattern: +CC-NUMBER


class ShopifyParser:
    def __init__(self, fetcher: Fetcher, base_url: str):
        self.fetcher = fetcher
        self.base_url = base_url.rstrip("/")

    async def fetch_homepage(self) -> Tuple[Optional[str], BeautifulSoup]:
        status, html = await self.fetcher.get_text(self.base_url)
        soup = soupify(html or "")
        return (html, soup)

    async def fetch_products_json(self) -> List[Dict]:
        """Fetch products.json across pages with safe caps (uses settings)."""
        all_products = []
        for page in range(1, settings.MAX_PRODUCTS_PAGES + 1):
            url = f"{self.base_url}/products.json?limit={settings.MAX_PRODUCTS_PAGE_LIMIT}&page={page}"
            status, text = await self.fetcher.get_text(url)
            if not text or status >= 400:
                break
            try:
                data = json.loads(text)
                items = data.get("products", [])
                if not items:
                    break
                all_products.extend(items)
                if len(items) < settings.MAX_PRODUCTS_PAGE_LIMIT:
                    break
            except json.JSONDecodeError:
                # stop on invalid json
                break
        return all_products

    @staticmethod
    def _map_products(raw: List[Dict]) -> List[Product]:
        """Local mapping fallback: maps raw Shopify product dicts to Product Pydantic objects."""
        products = []
        for p in raw:
            images = [img.get("src") for img in (p.get("images") or []) if img.get("src")]
            variants = p.get("variants") or []
            prices = [str(v.get("price")) for v in variants if v.get("price") is not None]
            price_range = None
            if prices:
                try:
                    floats = sorted({float(x) for x in prices})
                    if len(floats) == 1:
                        price_range = f"{floats[0]:.2f}"
                    else:
                        price_range = f"{floats[0]:.2f}-{floats[-1]:.2f}"
                except Exception:
                    price_range = None
            handle = p.get("handle")
            url = f"/products/{handle}" if handle else None
            products.append(
                Product(
                    id=p.get("id"),
                    title=p.get("title"),
                    handle=handle,
                    product_type=p.get("product_type"),
                    vendor=p.get("vendor"),
                    tags=[t.strip() for t in (p.get("tags", "").split(",") if isinstance(p.get("tags"), str) else p.get("tags") or []) if t.strip()],
                    url=url,
                    images=images,
                    price_range=price_range,
                )
            )
        return products

    def _extract_hero_products(self, soup: BeautifulSoup) -> List[Product]:
        prods = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if PRODUCT_LINK_PAT.search(href):
                title = a.get_text(strip=True) or None
                prods.append(Product(title=title, url=href))
        # dedupe by url
        seen = set()
        uniq = []
        for p in prods:
            key = p.url
            if key and key not in seen:
                uniq.append(p)
                seen.add(key)
        return uniq[:20]

    async def _fetch_policy(self, url: str, name: str) -> Optional[Policy]:
        status, text = await self.fetcher.get_text(url)
        if not text or status >= 400:
            return None
        soup = soupify(text)
        main = soup.find("main") or soup
        content = main.get_text(" ", strip=True)
        return Policy(title=name.title().replace("_", " "), url=url, content_text=clean_text(content)[:2000])

    async def extract(self) -> BrandContext:
        """
        Main extraction pipeline:
         - fetch homepage, products.json
         - gather small set of discovered links (footer/nav) to help the LLM
         - call LLM to produce final structured BrandContext JSON
         - validate with Pydantic and enforce strict phone formatting
        """
        # 1) fetch homepage + products json
        html, soup = await self.fetch_homepage()
        raw_products = await self.fetch_products_json()

        # 2) basic heuristics for discovered links to feed LLM
        link_map = find_links(
            soup,
            keywords=list({*FAQ_HINTS, *ABOUT_HINTS, *TRACK_HINTS, *BLOG_HINTS, *CONTACT_HINTS, "privacy", "return", "refund"})
        )

        # Build a small discovered_links list (absolutized)
        discovered_links = []
        for k, v in link_map.items():
            if v:
                discovered_links.append(absolutize(self.base_url, v))
        # include common policy routes as candidate probes (absolute)
        for route in COMMON_POLICY_ROUTES:
            discovered_links.append(self.base_url + route)
        # unique
        discovered_links = unique_keep_order(discovered_links)[:20]

        # 3) build system / user prompts for the LLM
        # truncate HTML to safe size to keep tokens reasonable
        homepage_snippet = (html or "")[:30000]
        # Trim products to a reasonable count in prompt
        sample_products = raw_products[:300]  # adjust if needed

        system_prompt = """
You are a data extraction assistant. You will be given:
- homepage_html: raw HTML string of the homepage,
- products_json: an array of product objects from Shopify's /products.json,
- discovered_links: helpful absolute links (faq, about, policies, etc.),
- base_url: the store's base url.

Your job: extract and normalize the store's information into a strict JSON object following this schema exactly:

{
  "website_url": "<string>",
  "brand_name": "<string|null>",
  "hero_products": [ { "title": "<string|null>", "handle": "<string|null>", "url": "<string|null>", "images": ["..."], "price_range": "<string|null>" } ],
  "product_catalog": [ { "id": int|null, "title": "<string|null>", "handle": "<string|null>", "product_type": "<string|null>", "vendor":"<string|null>", "tags":[...], "url":"<string|null>", "images":[...], "price_range":"<string|null>" } ],
  "privacy_policy": { "title":"<string>", "url":"<string|null>", "content_text":"<string|null>" } | null,
  "return_refund_policy": { "title":"<string>", "url":"<string|null>", "content_text":"<string|null>" } | null,
  "faqs": [ { "question":"<string>", "answer":"<string>" } ],
  "social_handles": { "instagram":"<string|null>", "facebook":"<string|null>", "tiktok":"<string|null>", "twitter":"<string|null>", "youtube":"<string|null>", "pinterest":"<string|null>", "linkedin":"<string|null>" },
  "contact_info": { "emails":[...], "phones":[...] },
  "about_text": "<string|null>",
  "important_links": { "order_tracking":"<string|null>", "contact_us":"<string|null>", "blog":"<string|null>", "privacy":"<string|null>", "returns":"<string|null>", "faq":"<string|null>", "about":"<string|null>" },
  "raw_meta": {}
}

IMPORTANT RULES:
1) Return ONLY valid JSON (no surrounding commentary).
2) Phone numbers must strictly follow the format: +<country_code>-<number> (dash required). Country code 1-3 digits; number 7-15 digits. If you cannot produce this normalized form for a phone, omit it.
3) Keep text trimmed. Limit policy content_text and about_text to 2000 characters.
4) If a field is not found, use null or an empty list as appropriate.
5) Prefer absolute URLs where possible.
6) For product_catalog, include as many products as available but if there are many, return at most 1000 entries in the JSON output.
"""

        # Compose a user prompt containing the inputs (JSON-encoded)
        user_prompt = f"""
homepage_html: '''{homepage_snippet}'''
products_json: {json.dumps(sample_products, ensure_ascii=False)}
discovered_links: {json.dumps(discovered_links)}
base_url: {self.base_url}

Produce the JSON matching the schema exactly. Output ONLY the JSON.
"""

        # 4) Call LLM in a thread (call_groq_llm is blocking)
        try:
            structured = await asyncio.get_event_loop().run_in_executor(
                None, call_groq_llm, system_prompt, user_prompt, 0.0
            )
        except GroqLLMError as e:
            raise ParsingError(f"LLM extraction failed: {e}")
        except Exception as e:
            raise ParsingError(f"Unexpected LLM error: {e}")

        if not isinstance(structured, dict):
            raise ParsingError("LLM did not return a JSON object as expected.")

        # 5) Validate & coerce to Pydantic BrandContext
        try:
            ctx = BrandContext.model_validate(structured)
        except Exception as e:
            # include a short dump of structured for debugging (but not too large)
            s = json.dumps(structured)[:2000]
            raise ParsingError(f"LLM returned invalid schema: {e}. Partial output: {s}")

        # 6) Final enforcement: strict phone pattern (as safety net)
        try:
            phones_raw = ctx.contact_info.phones or []
            phones_clean = [p for p in phones_raw if isinstance(p, str) and PHONE_STRICT.match(p)]
            # Update the model instance field
            ctx.contact_info.phones = phones_clean
        except Exception:
            # If something unexpected, just clear phones to be safe
            ctx.contact_info.phones = []

        # 7) Ensure important_links are absolute where present (best effort)
        try:
            il = ctx.important_links
            for attr in ["order_tracking", "contact_us", "blog", "privacy", "returns", "faq", "about"]:
                val = getattr(il, attr, None)
                if val:
                    setattr(il, attr, absolutize(self.base_url, val))
        except Exception:
            pass

        # 8) Done
        return ctx
