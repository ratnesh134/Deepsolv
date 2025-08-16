import json, re, asyncio
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from app.services.fetcher import Fetcher
from app.services.html_utils import (
    soupify, find_links, absolutize, extract_emails_phones,
    extract_socials, extract_jsonld_faqs, extract_brand_name
)
from app.services.normalizer import clean_text, unique_keep_order
from app.config import settings
from app.models.schemas import (
    Product, Policy, FAQItem, SocialHandles, ContactInfo,
    ImportantLinks, BrandContext
)

POLICY_KEYWORDS = {
    "privacy": ["privacy", "privacy-policy"],
    "refund": ["return", "refund", "returns", "return-policy", "refund-policy"],
}
COMMON_POLICY_ROUTES = [
    "/policies/privacy-policy",
    "/policies/refund-policy",
    "/policies/shipping-policy",
]

FAQ_HINTS = ["faq", "faqs", "help", "support"]
ABOUT_HINTS = ["about", "our story", "about us"]
TRACK_HINTS = ["track", "order tracking", "track order"]
BLOG_HINTS = ["blog", "blogs", "journal"]
CONTACT_HINTS = ["contact", "contact us", "support"]

PRODUCT_LINK_PAT = re.compile(r"/products/[^/]+/?$", re.I)

class ShopifyParser:
    def __init__(self, fetcher: Fetcher, base_url: str):
        self.fetcher = fetcher
        self.base_url = base_url

    async def fetch_homepage(self) -> Tuple[Optional[str], BeautifulSoup]:
        status, html = await self.fetcher.get_text(self.base_url)
        soup = soupify(html or "")
        return (html, soup)

    async def fetch_products_json(self) -> List[Dict]:
        # /products.json?limit=250&page=1..N
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
                break
        return all_products

    @staticmethod
    def _map_products(raw: List[Dict]) -> List[Product]:
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
                except:
                    price_range = None
            url = None
            handle = p.get("handle")
            if handle:
                url = f"/products/{handle}"
            products.append(Product(
                id=p.get("id"),
                title=p.get("title"),
                handle=handle,
                product_type=p.get("product_type"),
                vendor=p.get("vendor"),
                tags=[t.strip() for t in (p.get("tags","").split(",") if isinstance(p.get("tags"), str) else p.get("tags") or []) if t.strip()],
                url=url,
                images=images,
                price_range=price_range
            ))
        return products

    def _extract_hero_products(self, soup: BeautifulSoup) -> List[Product]:
        prods = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if PRODUCT_LINK_PAT.search(href):
                title = a.get_text(strip=True) or None
                prods.append(Product(title=title, url=href))
        # unique by url
        seen = set()
        uniq = []
        for p in prods:
            key = p.url
            if key and key not in seen:
                uniq.append(p)
                seen.add(key)
        return uniq[:20]  # sanity cap

    async def _fetch_policy(self, url: str, name: str) -> Optional[Policy]:
        status, text = await self.fetcher.get_text(url)
        if not text or status >= 400:
            return None
        soup = soupify(text)
        main = soup.find("main") or soup
        content = main.get_text(" ", strip=True)
        return Policy(title=name.title().replace("_", " "), url=url, content_text=clean_text(content)[:2000])

    async def extract(self) -> BrandContext:
        html, soup = await self.fetch_homepage()

        brand_name = extract_brand_name(soup)

        # Important links and pages
        link_map = find_links(
            soup,
            keywords=list({*FAQ_HINTS, *ABOUT_HINTS, *TRACK_HINTS, *BLOG_HINTS, *CONTACT_HINTS, "privacy", "return", "refund"})
        )
        def pick_url(keys: List[str]) -> Optional[str]:
            for k in keys:
                if k in link_map:
                    return link_map[k]
            return None

        important = ImportantLinks(
            faq=pick_url(FAQ_HINTS),
            about=pick_url(ABOUT_HINTS),
            order_tracking=pick_url(TRACK_HINTS),
            blog=pick_url(BLOG_HINTS),
            contact_us=pick_url(CONTACT_HINTS),
        )

        # Normalize/absolutize known policy links or probe common policy routes
        privacy_url = important.privacy or None
        refund_url = important.returns or None

        if not privacy_url:
            for route in COMMON_POLICY_ROUTES:
                if "privacy" in route:
                    privacy_url = route
                    break
        if not refund_url:
            for route in COMMON_POLICY_ROUTES:
                if "refund" in route or "return" in route:
                    refund_url = route
                    break

        if privacy_url:
            privacy_url = absolutize(self.base_url, privacy_url)
        if refund_url:
            refund_url = absolutize(self.base_url, refund_url)

        # Gather contacts/socials from homepage html
        emails, phones = extract_emails_phones(html or "")
        socials = extract_socials(html or "")

        # Try about text
        about_text = None
        if important.about:
            status, txt = await self.fetcher.get_text(absolutize(self.base_url, important.about))
            if txt and status < 400:
                s2 = soupify(txt)
                main = s2.find("main") or s2
                about_text = clean_text(main.get_text(" ", strip=True))[:2000]

        # FAQs: json-ld or explicit FAQ page
        faqs = []
        faqs.extend([FAQItem(**x) for x in extract_jsonld_faqs(soup)])
        if not faqs and important.faq:
            status, txt = await self.fetcher.get_text(absolutize(self.base_url, important.faq))
            if txt and status < 400:
                s3 = soupify(txt)
                faqs.extend([FAQItem(**x) for x in extract_jsonld_faqs(s3)])
                # fallback: simplistic Q/A extraction
                if not faqs:
                    qa = []
                    for el in s3.select("h2,h3"):
                        q = el.get_text(" ", strip=True)
                        nxt = el.find_next_sibling()
                        if q and nxt:
                            a = nxt.get_text(" ", strip=True)
                            if a:
                                qa.append(FAQItem(question=q, answer=a[:600]))
                    faqs = qa[:20]

        # Policies contents
        privacy_policy = await self._fetch_policy(privacy_url, "privacy_policy") if privacy_url else None
        return_policy  = await self._fetch_policy(refund_url,  "return_refund_policy") if refund_url else None

        # Product catalog via products.json
        raw_products = await self.fetch_products_json()
        catalog = self._map_products(raw_products)

        # Hero products (homepage links)
        hero = self._extract_hero_products(soup)

        # Fill important links with absolutized values if present
        def abs_or_none(u): return absolutize(self.base_url, u) if u else None
        important.privacy = privacy_policy.url if privacy_policy else abs_or_none(link_map.get("privacy"))
        important.returns = return_policy.url if return_policy else abs_or_none(link_map.get("return") or link_map.get("refund"))
        important.faq = abs_or_none(important.faq) if important.faq else None
        important.about = abs_or_none(important.about) if important.about else None
        important.blog = abs_or_none(important.blog) if important.blog else None
        important.order_tracking = abs_or_none(important.order_tracking) if important.order_tracking else None
        important.contact_us = abs_or_none(important.contact_us) if important.contact_us else None

        # Dedup & finalize
        emails = unique_keep_order(emails)
        phones = unique_keep_order(phones)

        ctx = BrandContext(
            website_url=self.base_url,
            brand_name=brand_name,
            hero_products=hero,
            product_catalog=catalog,
            privacy_policy=privacy_policy,
            return_refund_policy=return_policy,
            faqs=faqs,
            social_handles=SocialHandles(**socials),
            contact_info=ContactInfo(emails=emails, phones=phones),
            about_text=about_text,
            important_links=important,
            raw_meta={}
        )
        return ctx
