from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any

class Product(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    handle: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: List[str] = []
    url: Optional[str] = None
    images: List[str] = []
    price_range: Optional[str] = None  # derived from variants

class FAQItem(BaseModel):
    question: str
    answer: str

class Policy(BaseModel):
    title: str
    url: Optional[str] = None
    content_text: Optional[str] = None

class SocialHandles(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    pinterest: Optional[str] = None
    linkedin: Optional[str] = None

class ContactInfo(BaseModel):
    emails: List[str] = []
    phones: List[str] = []

class ImportantLinks(BaseModel):
    order_tracking: Optional[str] = None
    contact_us: Optional[str] = None
    blog: Optional[str] = None
    returns: Optional[str] = None
    privacy: Optional[str] = None
    faq: Optional[str] = None
    about: Optional[str] = None

class BrandContext(BaseModel):
    website_url: str
    brand_name: Optional[str] = None
    hero_products: List[Product] = []
    product_catalog: List[Product] = []
    privacy_policy: Optional[Policy] = None
    return_refund_policy: Optional[Policy] = None
    faqs: List[FAQItem] = []
    social_handles: SocialHandles = SocialHandles()
    contact_info: ContactInfo = ContactInfo()
    about_text: Optional[str] = None
    important_links: ImportantLinks = ImportantLinks()
    raw_meta: Dict[str, Any] = {}

class ExtractRequest(BaseModel):
    website_url: HttpUrl = Field(..., description="Brand's Shopify store URL")
