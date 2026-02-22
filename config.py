"""
config.py — Central configuration for the Image Scraper app.

All sensitive values (MongoDB URI) are read from environment variables
so credentials are never hard-coded in source.  Copy .env.example to .env
and fill in your own values before running the app.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file if present (ignored in production where env vars are set directly)

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB: str = os.getenv("MONGO_DB", "image_scrap")
MONGO_COLLECTION: str = os.getenv("MONGO_COLLECTION", "scraped_images")

# ── Scraper ───────────────────────────────────────────────────────────────────
# Images are saved under static/ so Flask can serve them at /static/images/…
SAVE_DIRECTORY: str = os.path.join("static", "images")
MAX_IMAGES: int = int(os.getenv("MAX_IMAGES", "20"))

# Request timeout (seconds) for both the search page and individual image downloads
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "10"))

# A modern browser User-Agent is essential — Google returns a much simpler
# (bot-friendly) page for unknown agents which has fewer embedded image URLs.
HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# ── Scrape backend ───────────────────────────────────────────────────────────
# Set to "selenium" to use headless Chrome (more reliable, slower).
# Set to "requests" to use the lightweight HTTP + regex strategy (faster, fragile).
# If Selenium is selected but fails (e.g. ChromeDriver not installed) the app
# automatically falls back to the requests strategy.
SCRAPE_BACKEND: str = os.getenv("SCRAPE_BACKEND", "requests")

# How many times to scroll the Google Images page in Selenium mode.
# Each scroll loads ~20 more images.
SELENIUM_SCROLLS: int = int(os.getenv("SELENIUM_SCROLLS", "3"))

# Seconds to wait after each scroll for images to load.
SELENIUM_SCROLL_PAUSE: float = float(os.getenv("SELENIUM_SCROLL_PAUSE", "1.5"))

# ── Flask ─────────────────────────────────────────────────────────────────────
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production")
DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
