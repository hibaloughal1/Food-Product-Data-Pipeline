# Food Product Data Pipeline

A data engineering pipeline that scrapes food product prices and promotions from Moroccan retail chains, cleans and validates the collected data, stores it with price history, and serves it through a Flask dashboard.

This was built as an academic data engineering project focused on retail price monitoring.

## Architecture

Five independent modules connected by one pipeline:

```
Web Scraping / Catalogue Extraction (OCR)
        ↓
Cleaning
        ↓
Validation
        ↓
Database (price history)
        ↓
Dashboard
```

```
├── app.py                     # Flask dashboard + internal API
├── config.py                  # Centralized configuration (via env vars)
├── database.py                # SQLAlchemy connection (SQLite by default / MySQL)
├── models.py                  # ORM models (Enseigne/Produit/HistoriquePrix/Scraping/Utilisateur)
├── seed_demo_data.py          # Generates realistic demo data
│
├── scraping/
│   ├── scraper_base.py            # Common base class for all scrapers
│   ├── scraper_catalogue_web.py   # Real, functional scraper (see below)
│   ├── scraper_bim.py             # Example connector — direct e-commerce site
│   ├── scraper_marjane.py         # Example connector — direct e-commerce site
│   ├── scraper_dynamic_template.py  # Playwright template for JS-rendered sites
│   └── catalogue_pdf.py           # PDF extraction + OCR (Tesseract)
│
├── tests_fixtures/              # Fixed real content for reproducible tests
├── test_scraper_catalogue_web.py
│
├── processing/
│   ├── nettoyage.py            # Cleaning rules
│   ├── validation.py           # Validation rules
│   └── pipeline.py             # Full orchestrator (scraping → database)
│
├── templates/dashboard.html    # Dashboard UI (Bootstrap)
├── static/css/style.css
├── static/js/dashboard.js      # API calls + Chart.js charts
└── requirements.txt
```

## Scraping Approach

Before writing any scraper, the actual accessibility of each retailer's site was checked directly:

- **BIM** has no e-commerce site at all — its promotions are only published as weekly catalogues in image/PDF form.
- **Marjane.ma** has a real online store, but it's a React SPA behind anti-bot protection that blocks plain HTTP requests.

Given that, the scraper actually used (`scraping/scraper_catalogue_web.py`) targets **hmizate.ma**, a site that republishes the weekly catalogue content of several chains (BIM, Marjane, Kazyon, Carrefour, Aswak Assalam) as structured text articles with real prices. It follows section headings to determine the product department, extracts (name, price, promo price) pairs, and filters strictly for food products, excluding non-food departments (appliances, pool/summer goods, hygiene, etc.).

The extraction logic is validated against real, fixed content: `test_scraper_catalogue_web.py` checks it against a real article fixture captured from the site (in `tests_fixtures/`).

A PDF/OCR path (`scraping/catalogue_pdf.py`, using pdfplumber with an OCR fallback) is also included for manually downloaded catalogue PDFs. Two example direct-site connectors (`scraper_bim.py`, `scraper_marjane.py`) are included as templates for retailers with an accessible, non-protected e-commerce site.

All scraping respects a default 2-second delay between requests to the same site (`config.py`).

## Technologies

Flask, SQLAlchemy, requests, BeautifulSoup, lxml, pdfplumber, pytesseract, Pillow, pandas, openpyxl.

## Data

This repository does not include the real dataset collected during the project (the local SQLite database, logs, and downloaded catalogues/images are excluded via `.gitignore`).

Running `python seed_demo_data.py` instead generates a **synthetic** demo dataset (4 retail chains × 26 products × 15 days of price history) so the dashboard can be explored immediately. This generated data is for demonstration only and is not the data that was actually collected.

## Installation

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

For OCR extraction of scanned PDF catalogues, also install the Tesseract binary (see [UB-Mannheim's Windows build](https://github.com/UB-Mannheim/tesseract/wiki), or your OS package manager).

## Configuration

By default the project uses SQLite (`data/products.db`, created automatically). To use MySQL instead, set `DATABASE_URL`:

```bash
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/dbname"
```

Never commit real database credentials.

## Usage

**With demo data:**

```bash
python seed_demo_data.py
python app.py
# http://127.0.0.1:5000
```

**With a real scrape** (requires internet access to hmizate.ma):

```bash
python test_scraper_catalogue_web.py       # sanity-check the parser
python -m processing.pipeline --enseigne bim
python -m processing.pipeline --toutes      # all chains at once
python app.py
```

The dashboard includes KPIs, charts (products per chain, category breakdown, cheapest products, promotions), price comparison, a filterable product table, and CSV/Excel export.

## Limitations

No LICENSE is currently included. `SECRET_KEY`/`DEBUG` in `config.py` default to development-friendly values and must be overridden via environment variables before any real deployment. Automated collection scheduling (e.g. via cron) is documented but not built into the application itself.

## Future Improvements

- User authentication (the `Utilisateur` model already exists).
- Image-based product/catalogue matching via computer vision.
- Price-trend forecasting on the stored price history.
- Automated email alerts on significant price changes.
- Containerized deployment with a managed MySQL instance.
