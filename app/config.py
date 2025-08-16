from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Shopify Insights Fetcher"
    TIMEOUT_SECS: float = 20.0
    RETRIES: int = 2
    USER_AGENT: str = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    ENABLE_DB: bool = False
    DATABASE_URL: Optional[str] = None  # e.g. mysql+pymysql://user:pass@host:3306/db
    MAX_PRODUCTS_PAGE_LIMIT: int = 250
    MAX_PRODUCTS_PAGES: int = 10  # safety
    REQUEST_CONCURRENCY: int = 5

    class Config:
        env_file = ".env"

settings = Settings()
