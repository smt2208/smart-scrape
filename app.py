"""
app.py — Flask application entry point.

This file intentionally contains only route definitions.
All scraping logic lives in scraper.py and all database I/O lives in db.py,
keeping concerns cleanly separated.

Route overview
--------------
GET  /          Homepage — renders the search form.
POST /scrape    Accepts the search query, scrapes Google Images, saves files,
                persists metadata to MongoDB, and renders the results page.
"""

import logging

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_cors import CORS

import config
from db import save_metadata
from scraper import scrape_and_save

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename="scrapper.log",
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
CORS(app)  # enable cross-origin requests (useful when calling the API from JS)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def homepage():
    """Render the search form."""
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    """
    Handle the search-form submission.

    Workflow:
      1. Validate the query string.
      2. Call scrape_and_save() — fetches image URLs and downloads files.
      3. Persist lightweight metadata (not image bytes) to MongoDB.
      4. Render result.html with the list of saved images.
    """
    query = request.form.get("content", "").strip()

    if not query:
        flash("Please enter a search term before clicking Search.", "warning")
        return redirect(url_for("homepage"))

    try:
        logger.info("Scrape request received for query: '%s'", query)
        records = scrape_and_save(query)

        if not records:
            flash(f"No images could be downloaded for '{query}'. Try a different term.", "warning")
            return redirect(url_for("homepage"))

        # Persist metadata to MongoDB (non-critical — page still renders on failure)
        db_ok = save_metadata(records)
        if not db_ok:
            flash("Images downloaded, but metadata could not be saved to the database.", "info")

        logger.info("Returning %d images for query '%s'.", len(records), query)
        return render_template("result.html", query=query, images=records)

    except ValueError as exc:
        # Raised by scrape_and_save when no URLs were found
        flash(str(exc), "warning")
        return redirect(url_for("homepage"))

    except Exception as exc:
        logger.exception("Unhandled error while scraping '%s': %s", query, exc)
        flash("Something went wrong during scraping. Check scrapper.log for details.", "danger")
        return redirect(url_for("homepage"))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)

