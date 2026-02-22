# Image Scraper

A Flask web application that searches Google Images for a keyword, downloads the results to disk, and displays them in a responsive image grid. Supports two interchangeable scraping backends — a fast `requests` + regex approach and a robust headless-Chrome `Selenium` approach — with automatic fallback between them.

---

## Features

- **Dual-backend scraping** — switch between `requests` (fast, no browser) and `Selenium` (reliable, scrollable) via a single env var.
- **Auto-fallback** — if Selenium/Chrome isn't available the app silently falls back to the `requests` backend so it always works.
- **MongoDB metadata storage** — stores lightweight image metadata (URL, filename, query) rather than raw bytes.
- **Flask-served images** — downloaded images live in `static/images/` and are served directly by Flask.
- **Responsive UI** — dark-themed CSS Grid layout with hover effects and source links.
- **Secrets-free config** — all credentials and settings are read from environment variables / `.env`.

---

## Project structure

```
├── app.py              # Flask routes (thin layer)
├── scraper.py          # Scraping logic — requests & Selenium backends
├── db.py               # MongoDB persistence (metadata only)
├── config.py           # All settings, read from .env
├── requirements.txt
├── .env.example        # Template — copy to .env and fill in values
├── static/
│   ├── css/style.css
│   └── images/         # Downloaded images (git-ignored)
└── templates/
    ├── base.html
    ├── index.html      # Search form
    └── result.html     # Image grid results
```

---

## Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env   # Windows
# or
cp .env.example .env     # macOS / Linux
```

Then open `.env` and set at minimum:

```
MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/...
SECRET_KEY=<random-string>
```

### 3. Run

```bash
python app.py
```

Open http://localhost:5000 in your browser.

---

## Scraping backends

| Setting | Value | Description |
|---|---|---|
| `SCRAPE_BACKEND` | `requests` *(default)* | Fast, no browser needed |
| `SCRAPE_BACKEND` | `selenium` | Headless Chrome, scrolls for more images |
| `SELENIUM_SCROLLS` | `3` *(default)* | How many times to scroll the results page |
| `SELENIUM_SCROLL_PAUSE` | `1.5` *(default)* | Seconds to wait between scrolls |
| `MAX_IMAGES` | `20` *(default)* | Max images to download per search |

To use the Selenium backend, Chrome must be installed on your machine. ChromeDriver is downloaded automatically by `webdriver-manager`.

---

## Tech stack

- **Backend** — Python, Flask, Flask-CORS
- **Scraping** — requests, Selenium (optional), webdriver-manager
- **Database** — MongoDB (via pymongo)
- **Frontend** — Jinja2 templates, vanilla CSS Grid

---

## Disclaimer

This tool is intended for educational and personal use only. Scraping Google Images may violate Google's Terms of Service. Always respect website terms of service and applicable copyright laws before downloading or using images.
