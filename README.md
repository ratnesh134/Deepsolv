# Deepsolv

# Shopify Insights Fetcher

## 📌 Overview

Shopify Insights Fetcher is a Python-based application that scrapes product, collection, and pricing data from a Shopify store and provides structured results via a REST API.
It uses FastAPI for the backend and a custom HTML parsing logic for extracting data.

## 🚀 Features

Shopify Data Parsing: Extracts homepage, collections, and product details from a Shopify store.

HTML-based Extraction: Uses regex and HTML parsing to get store insights.

FastAPI Backend: API endpoints to fetch processed Shopify data.

Environment-based Configuration: Secure settings with .env.

## Project Demo
[Demo](https://drive.google.com/file/d/1XEpOqu5dJcpdseU0oSA5Q1-28LuerD0y/view?usp=sharing)

## 📂 Project Structure

```
shopify-insights/
├─ app/
│  ├─ main.py                 # FastAPI app & routes
│  ├─ config.py               # settings (env, timeouts, db url)
│  ├─ models/
│  │  ├─ schemas.py           # Pydantic response/request models
│  │  └─ db_models.py         # SQLAlchemy ORM models (bonus)
│  ├─ services/
│  │  ├─ fetcher.py           # robust HTTP client (retries, headers)
│  │  ├─ parser_shopify.py    # Shopify-aware parsing (products.json, policies, ...)
│  │  ├─ html_utils.py        # BeautifulSoup helpers, JSON-LD/FAQ extractors
│  │  ├─ normalizer.py        # text cleanup, URL normalization
│  │  └─ competitors.py       # simple competitor discovery (bonus)
│  ├─ db/
│  │  ├─ session.py           # SQLAlchemy engine/session factory
│  │  └─ repo.py              # persistence interface (bonus)
│  ├─ exceptions.py           # typed exceptions → API errors
│  └─ logging_conf.py         # structured logging
├─ requirements.txt
├─ .env.example
├─ README.md

```


⚙️ Installation

Clone the repository

```
git clone [https://github.com/ratnesh134/Deepsolv.git](https://github.com/ratnesh134/Deepsolv.git)`https://github.com/yourusername/shopify-insights-fetcher

```
cd shopify-insights-fetcher


Create a virtual environment

```
python3 -m venv venv
source venv/bin/activate
```

Install dependencies

```
pip install -r requirements.txt
```


▶️ Usage

Run the FastAPI server
```
uvicorn app.main:app --reload
```

Access API Docs
```
Visit: http://127.0.0.1:8000/docs
```

📡 Example API Call

POST /shopify/fetch
```
{
    "url": "https://examplestore.myshopify.com"
}
```

Response
```
{
    "store_name": "Example Store",
    "collections": ["New Arrivals", "Best Sellers"],
    "products": [
        {
            "name": "T-Shirt",
            "price": "$25",
            "url": "https://examplestore.myshopify.com/products/t-shirt"
        }
    ],
    "emails": ["contact@example.com"],
    "phones": ["+91-9876543210"]
}
```
