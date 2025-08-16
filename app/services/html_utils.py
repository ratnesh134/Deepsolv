import json, re
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Tuple

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,}\d)")

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"instagram\.com/[^\"'>\s]+", re.I),
    "facebook": re.compile(r"(facebook|fb)\.com/[^\"'>\s]+", re.I),
    "tiktok": re.compile(r"tiktok\.com/[^\"'>\s]+", re.I),
    "twitter": re.compile(r"(twitter|x)\.com/[^\"'>\s]+", re.I),
    "youtube": re.compile(r"youtube\.com/[^\"'>\s]+", re.I),
    "pinterest": re.compile(r"pinterest\.com/[^\"'>\s]+", re.I),
    "linkedin": re.compile(r"linkedin\.com/[^\"'>\s]+", re.I),
}

def soupify(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")

def extract_brand_name(soup: BeautifulSoup) -> Optional[str]:
    if soup.title and soup.title.text:
        return soup.title.text.strip().split("|")[0].strip()
    meta = soup.find("meta", attrs={"property": "og:site_name"})
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None

def find_links(soup: BeautifulSoup, keywords: List[str]) -> Dict[str, str]:
    links = {}
    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) or "").lower()
        href = a["href"].strip()
        for kw in keywords:
            if kw in text or kw in href.lower():
                links[kw] = href
    return links

def absolutize(base: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if not href.startswith("/"):
        return base.rstrip("/") + "/" + href
    return base.rstrip("/") + href

def extract_emails_phones(text: str) -> Tuple[List[str], List[str]]:
    # Extract emails
    emails = sorted(set(m.group(0) for m in EMAIL_RE.finditer(text)))
    
    # Extract raw phone numbers
    raw_phones = sorted(set(m.group(0) for m in PHONE_RE.finditer(text)))
    
    # Clean phone numbers
    cleaned_phones = []
    for num in raw_phones:
        num_str = re.sub(r"[^\d+]", "", num)  # Remove spaces, hyphens, non-digits except '+'
        if re.fullmatch(r"\+?\d{10}", num_str):  # Acceptable phone number length
            cleaned_phones.append(num_str)
    phones = list(set(cleaned_phones))  # Remove duplicates
    
    return emails, phones

def extract_socials(html: str) -> Dict[str, Optional[str]]:
    res = {}
    for key, pat in SOCIAL_PATTERNS.items():
        m = pat.search(html)
        res[key] = m.group(0) if m else None
    return res

def extract_jsonld_faqs(soup: BeautifulSoup) -> List[Dict[str, str]]:
    faqs = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except json.JSONDecodeError:
            continue
        # handle single or list
        blocks = data if isinstance(data, list) else [data]
        for obj in blocks:
            if obj.get("@type") == "FAQPage":
                for item in obj.get("mainEntity", []):
                    q = item.get("name") or item.get("question")
                    a_obj = item.get("acceptedAnswer") or {}
                    a = (a_obj.get("text") if isinstance(a_obj, dict) else None) or ""
                    if q and a:
                        faqs.append({"question": q.strip(), "answer": a.strip()})
    return faqs
