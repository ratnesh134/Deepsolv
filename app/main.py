import asyncio
from fastapi import FastAPI, HTTPException
from app.config import settings
from app.logging_conf import configure_logging
from app.models.schemas import ExtractRequest, BrandContext
from app.services.fetcher import Fetcher
from app.services.parser_shopify import ShopifyParser
from app.services.competitors import discover_competitors
from app.db.repo import save_brand_snapshot

configure_logging()
app = FastAPI(title=settings.APP_NAME)

@app.post("/extract", response_model=BrandContext)
async def extract_brand(req: ExtractRequest):
    fetcher = Fetcher()
    try:
        base = await fetcher.ensure_root_ok(str(req.website_url))
    except Exception as e:
        await fetcher.close()
        # Per assignment: 401 if website not found
        raise HTTPException(status_code=401, detail=f"Website not found: {e}")

    try:
        parser = ShopifyParser(fetcher, base)
        ctx = await parser.extract()
        payload = ctx.model_dump()
        # optional persistence
        save_brand_snapshot(base, payload)
        return ctx
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        await fetcher.close()

@app.post("/extract-with-competitors")
async def extract_with_competitors(req: ExtractRequest):
    fetcher = Fetcher()
    try:
        base = await fetcher.ensure_root_ok(str(req.website_url))
        parser = ShopifyParser(fetcher, base)
        ctx = await parser.extract()
        comp_urls = await discover_competitors(fetcher, base, ctx.brand_name, n=3)

        results = {"brand": ctx.model_dump(), "competitors": []}
        for cu in comp_urls:
            try:
                p = ShopifyParser(fetcher, cu)
                cctx = await p.extract()
                results["competitors"].append(cctx.model_dump())
                save_brand_snapshot(cu, cctx.model_dump())
            except Exception:
                continue
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
    finally:
        await fetcher.close()
