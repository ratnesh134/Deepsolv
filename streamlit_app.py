# streamlit_app.py
import streamlit as st
import requests
import json
import pandas as pd
from urllib.parse import urljoin
from typing import Dict, Any, List

st.set_page_config(page_title="Shopify Insights UI", layout="wide")

# Sidebar: configure FastAPI base URL
api_base = st.sidebar.text_input("FastAPI base URL", value="http://localhost:8000")
st.sidebar.markdown("Make sure your FastAPI app is running (uvicorn app.main:app --reload).")

def call_api(base_url: str, website_url: str, include_competitors: bool = False) -> Dict[str, Any]:
    endpoint = "/extract-with-competitors" if include_competitors else "/extract"
    url = base_url.rstrip("/") + endpoint
    resp = requests.post(url, json={"website_url": website_url}, timeout=60)
    # raise_for_status to present proper error messages to user
    resp.raise_for_status()
    return resp.json()

def absolutize(base: str, href: str) -> str:
    if not href:
        return ""
    # If already absolute, urljoin will just return href
    return urljoin(base, href)

def normalize_social_link(link: str) -> str:
    if not link:
        return ""
    if link.startswith("//"):
        return "https:" + link
    if link.startswith("http://") or link.startswith("https://"):
        return link
    # greedy fallback
    return "https://" + link

def show_brand(ctx: Dict[str, Any], title_prefix: str = "Brand"):
    website = ctx.get("website_url", "")
    brand_name = ctx.get("brand_name") or website
    st.subheader(f"{title_prefix}: {brand_name}")
    cols = st.columns([2, 1])

    # Left column: about / links
    with cols[0]:
        about = ctx.get("about_text")
        if about:
            st.markdown("**About**")
            st.write(about)
        links = ctx.get("important_links") or {}
        if any(links.values()):
            st.markdown("**Important links**")
            for k, v in links.items():
                if v:
                    st.markdown(f"- **{k.replace('_',' ').title()}**: [{v}]({absolutize(website, v)})")

        # Policies
        privacy = ctx.get("privacy_policy")
        returns = ctx.get("return_refund_policy")
        if privacy or returns:
            st.markdown("**Policies (preview)**")
            if privacy:
                st.markdown(f"- **Privacy**: {privacy.get('url') or ''}")
                st.write(privacy.get("content_text","")[:500] + ("..." if len(privacy.get("content_text",""))>500 else ""))
            if returns:
                st.markdown(f"- **Return/Refund**: {returns.get('url') or ''}")
                st.write(returns.get("content_text","")[:500] + ("..." if len(returns.get("content_text",""))>500 else ""))

        # Contact
        contact = ctx.get("contact_info") or {}
        emails = contact.get("emails", [])
        phones = contact.get("phones", [])
        if emails or phones:
            st.markdown("**Contact**")
            if emails:
                st.write("Emails:", ", ".join(emails))
            if phones:
                st.write("Phones:", ", ".join(phones))

        # Socials
        socials = ctx.get("social_handles") or {}
        if any(socials.values()):
            st.markdown("**Social handles**")
            for platform, link in socials.items():
                if link:
                    st.markdown(f"- **{platform.title()}**: [{normalize_social_link(link)}]({normalize_social_link(link)})")

    # Right column: quick stats
    with cols[1]:
        hero = ctx.get("hero_products") or []
        catalog = ctx.get("product_catalog") or []
        st.metric("Hero products (found)", len(hero))
        st.metric("Total products (catalog)", len(catalog))

    # FAQs
    faqs = ctx.get("faqs") or []
    if faqs:
        with st.expander("FAQs"):
            for f in faqs:
                q = f.get("question") or f.get("q") or ""
                a = f.get("answer") or f.get("a") or ""
                st.markdown(f"**Q:** {q}")
                st.write(a)

    # Hero product previews
    hero = ctx.get("hero_products") or []
    if hero:
        st.markdown("### Hero products (sample)")
        cols = st.columns(4)
        for i, p in enumerate(hero[:8]):
            c = cols[i % 4]
            with c:
                title = p.get("title") or p.get("handle") or ""
                url = absolutize(website, p.get("url") or "")
                images = p.get("images") or []
                img = images[0] if images else None
                if img:
                    try:
                        st.image(img, use_container_width=True, caption=title)
                    except Exception:
                        # fallback: show title only
                        st.write(title)
                else:
                    st.write(title)
                if url:
                    st.markdown(f"[View product]({url})")

    # Product catalog table
    catalog = ctx.get("product_catalog") or []
    if catalog:
        st.markdown("### Product catalog (table)")
        rows = []
        for p in catalog:
            rows.append({
                "title": p.get("title"),
                "handle": p.get("handle"),
                "vendor": p.get("vendor"),
                "price_range": p.get("price_range"),
                "url": absolutize(website, p.get("url") or ""),
                "images_count": len(p.get("images") or [])
            })
        df = pd.DataFrame(rows)
        st.dataframe(df.head(200), use_container_width=True)

        # product images sample grid
        st.markdown("Product images (sample)")
        sample_imgs = []
        for p in catalog:
            imgs = p.get("images") or []
            if imgs:
                sample_imgs.append((p.get("title"), imgs[0]))
            if len(sample_imgs) >= 12:
                break
        if sample_imgs:
            cols = st.columns(4)
            for i, (title, img) in enumerate(sample_imgs):
                c = cols[i % 4]
                with c:
                    try:
                        st.image(img, caption=title, use_container_width=True)
                    except Exception:
                        st.write(title)

def pretty_download_button(data: Dict[str, Any], filename: str = "brand_context.json"):
    s = json.dumps(data, indent=2, ensure_ascii=False)
    st.download_button("Download JSON", s, file_name=filename, mime="application/json")

# Page body
st.title("Shopify Insights — Streamlit UI")
st.markdown("Enter a Shopify store URL and press **Extract**. The app calls your FastAPI endpoints and displays the structured result.")

with st.form("extract_form"):
    website = st.text_input("Shopify store URL (e.g. https://memy.co.in)", value="", max_chars=512)
    include_competitors = st.checkbox("Include competitors (calls /extract-with-competitors)", value=False)
    submitted = st.form_submit_button("Extract")

if submitted:
    if not website:
        st.warning("Please enter a website URL.")
    else:
        try:
            with st.spinner("Calling API and parsing..."):
                result = call_api(api_base, website, include_competitors)
            # if competitors endpoint, structure is {"brand":..., "competitors":[...]}
            if include_competitors and isinstance(result, dict) and "brand" in result:
                main = result.get("brand")
                comps = result.get("competitors") or []
                show_brand(main, title_prefix="Brand (primary)")
                st.markdown("---")
                for i, c in enumerate(comps, start=1):
                    show_brand(c, title_prefix=f"Competitor #{i}")
                    st.markdown("---")
                pretty_download_button(result, filename=f"{website.replace('://','_')}_with_competitors.json")
                with st.expander("Raw JSON"):
                    st.json(result)
            else:
                # single brand flow
                show_brand(result, title_prefix="Brand")
                pretty_download_button(result, filename=f"{website.replace('://','_')}.json")
                with st.expander("Raw JSON"):
                    st.json(result)
        except requests.HTTPError as e:
            # try to show response body if available
            try:
                resp = e.response
                if resp is not None:
                    st.error(f"API error: {resp.status_code} — {resp.text}")
                else:
                    st.error(f"HTTP error: {e}")
            except Exception:
                st.error(f"HTTP error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

st.markdown("---")
st.caption("This UI only requires your FastAPI service; no backend changes required.")
