"""
scraper.py — Image scraping logic with two interchangeable backends.

Backends
--------
requests  (default, fast)
    Sends a single HTTP GET to the Google Images search page with a modern
    browser User-Agent.  Google embeds image metadata as JSON inside <script>
    tags; the "ou" (original URL) field contains the direct link to each image
    on the source website.  A regex extracts those URLs without running any JS.
    Pros: fast, no extra dependencies.
    Cons: fragile if Google changes their JSON schema; can't scroll for more.

selenium  (robust, slower)
    Launches a headless Chrome browser via selenium + webdriver-manager,
    navigates to Google Images, waits for JS to execute, then scrolls the page
    to load more results before extracting URLs from the rendered page source.
    Pros: executes real JS, can load hundreds of images by scrolling, harder to
    block. Cons: requires Chrome + ChromeDriver on the host, slower startup.

The active backend is controlled by the SCRAPE_BACKEND env var (default:
"requests").  If "selenium" is requested but ChromeDriver import fails (e.g.
the package isn't installed), the app automatically falls back to "requests"
and logs a warning — so the app always works even without Chrome installed.
"""

import os
import re
import time
import logging
import requests

from config import (
    HEADERS,
    SAVE_DIRECTORY,
    MAX_IMAGES,
    REQUEST_TIMEOUT,
    SCRAPE_BACKEND,
    SELENIUM_SCROLLS,
    SELENIUM_SCROLL_PAUSE,
)

logger = logging.getLogger(__name__)

# ── Shared helpers ────────────────────────────────────────────────────────────

# Google stores original image URLs under the "ou" key in inline JSON.
_OU_PATTERN = re.compile(r'"ou":"(https?://[^"]+)"')

# Fallback: match any HTTPS URL ending with an image extension.
_FALLBACK_PATTERN = re.compile(
    r'https?://[^\s\'"<>]+\.(?:jpg|jpeg|png|webp|gif)',
    re.IGNORECASE,
)

# Google-owned domains — we skip these to keep only third-party image URLs.
_SKIP_DOMAINS = ("google.", "gstatic.", "googleapis.", "googleusercontent.")


def _build_search_url(query: str) -> str:
    return (
        f"https://www.google.com/search"
        f"?q={requests.utils.quote(query)}&tbm=isch&hl=en&safe=off"
    )


def _is_external_image(url: str) -> bool:
    """Return True if *url* points to a third-party host (not Google infra)."""
    return not any(d in url for d in _SKIP_DOMAINS)


def _extract_urls(html: str, max_images: int) -> list:
    """
    Extract and de-duplicate image URLs from raw HTML / page source.
    Tries the ``"ou":"…"`` JSON pattern first; falls back to extension regex.
    """
    urls = _OU_PATTERN.findall(html)
    if not urls:
        logger.warning("Primary pattern matched 0 URLs — using extension fallback.")
        urls = _FALLBACK_PATTERN.findall(html)

    seen: set = set()
    unique: list = []
    for url in urls:
        if url not in seen and _is_external_image(url):
            seen.add(url)
            unique.append(url)
    logger.info("Extracted %d unique external URLs.", len(unique))
    return unique[:max_images]


# ── Backend: requests ─────────────────────────────────────────────────────────

def _fetch_urls_requests(query: str, max_images: int) -> list:
    """
    Fetch Google Images search results using a plain HTTP request.

    No browser is launched.  Works by sending a GET with a Chrome User-Agent
    then regex-extracting the embedded JSON image data from the static HTML.
    """
    search_url = _build_search_url(query)
    logger.info("[requests] GET %s", search_url)

    response = requests.get(search_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    return _extract_urls(response.text, max_images)


# ── Backend: selenium ─────────────────────────────────────────────────────────

def _fetch_urls_selenium(query: str, max_images: int) -> list:
    """
    Fetch Google Images search results using a headless Chrome browser.

    Steps:
      1. Auto-download the correct ChromeDriver version via webdriver-manager.
      2. Open Google Images in a headless window.
      3. Scroll SELENIUM_SCROLLS times, pausing between each scroll to let
         lazy-loaded image data appear in the page source.
      4. Extract image URLs from the fully-rendered page source using the same
         regex patterns used by the requests backend.

    Raises:
        ImportError: if selenium or webdriver-manager is not installed.
        Exception:   for any WebDriver / Chrome launch error.
    """
    # Import here so the whole module doesn't break when selenium isn't installed.
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    search_url = _build_search_url(query)
    logger.info("[selenium] Launching headless Chrome → %s", search_url)

    options = Options()
    options.add_argument("--headless=new")          # headless mode (Chrome ≥ 112)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    # Suppress "Chrome is being controlled by automated software" banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(search_url)

        # Wait until at least one image thumbnail is present in the DOM.
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img.rg_i, img.Q4LuWd"))
        )
        logger.info("[selenium] Page loaded, starting scroll sequence (%d scrolls).", SELENIUM_SCROLLS)

        # Scroll to progressively reveal lazy-loaded image data.
        for i in range(SELENIUM_SCROLLS):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SELENIUM_SCROLL_PAUSE)
            logger.debug("[selenium] Scroll %d/%d complete.", i + 1, SELENIUM_SCROLLS)

        page_source = driver.page_source
        logger.info("[selenium] Page source captured (%d chars).", len(page_source))

    finally:
        driver.quit()
        logger.info("[selenium] Browser closed.")

    return _extract_urls(page_source, max_images)


# ── Strategy selector ─────────────────────────────────────────────────────────

def fetch_image_urls(query: str, max_images: int = MAX_IMAGES) -> list:
    """
    Fetch image URLs for *query* using the backend configured in SCRAPE_BACKEND.

    If the selenium backend is requested but cannot be initialised (missing
    package, no Chrome installed, etc.), the function automatically retries
    with the requests backend so the app remains functional.
    """
    backend = SCRAPE_BACKEND.lower()

    if backend == "selenium":
        try:
            return _fetch_urls_selenium(query, max_images)
        except ImportError:
            logger.warning(
                "selenium / webdriver-manager not installed. "
                "Falling back to requests backend. "
                "Run: pip install selenium webdriver-manager"
            )
        except Exception as exc:
            logger.warning(
                "Selenium backend failed (%s). Falling back to requests.", exc
            )
        # Fall through to requests
        return _fetch_urls_requests(query, max_images)

    # Default: requests
    return _fetch_urls_requests(query, max_images)


# ── Download ──────────────────────────────────────────────────────────────────

def download_image(image_url: str, save_path: str) -> bool:
    """
    Stream-download the image at *image_url* and write it to *save_path*.

    Validates Content-Type so we don't save HTML error pages as .jpg files.
    Returns True on success, False on any error.
    """
    try:
        resp = requests.get(
            image_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "image" not in content_type and "octet-stream" not in content_type:
            logger.warning(
                "Skipping %s — unexpected Content-Type: %s", image_url, content_type
            )
            return False

        with open(save_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)

        logger.info("Saved → %s", save_path)
        return True

    except Exception as exc:
        logger.warning("Download failed for %s: %s", image_url, exc)
        return False


# ── Pipeline ──────────────────────────────────────────────────────────────────

def scrape_and_save(query: str, max_images: int = MAX_IMAGES) -> list:
    """
    Full pipeline: fetch URLs → download → return metadata list.

    Each entry in the returned list has:
        query, index, url, filename, static_path, backend

    Raises:
        ValueError: if no image URLs were found for the query.
        requests.RequestException: propagated on unrecoverable HTTP errors.
    """
    os.makedirs(SAVE_DIRECTORY, exist_ok=True)
    safe_query = re.sub(r"\W+", "_", query).strip("_")
    backend_used = SCRAPE_BACKEND.lower()

    image_urls = fetch_image_urls(query, max_images)
    if not image_urls:
        raise ValueError(f"No image URLs found for query: '{query}'")

    results: list = []
    for index, url in enumerate(image_urls):
        filename = f"{safe_query}_{index}.jpg"
        save_path = os.path.join(SAVE_DIRECTORY, filename)

        if download_image(url, save_path):
            results.append(
                {
                    "query": query,
                    "index": index,
                    "url": url,
                    "filename": filename,
                    "static_path": f"images/{filename}",
                    "backend": backend_used,
                }
            )

    logger.info(
        "[%s] %d/%d images saved for '%s'.",
        backend_used, len(results), len(image_urls), query,
    )
    return results
