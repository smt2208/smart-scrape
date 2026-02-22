"""
db.py — MongoDB persistence layer.

We store only lightweight metadata (query, index, source URL, local filename)
rather than raw image bytes.  Storing binary image data in MongoDB is
impractical because:
  • Each BSON document is capped at 16 MB.
  • Large blobs make queries slow and backups large.
  • The filesystem (static/images/) already holds the files and Flask can serve
    them as static assets with zero extra work.
"""

import logging
import pymongo
from pymongo.errors import ConnectionFailure, OperationFailure

from config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

logger = logging.getLogger(__name__)


def get_collection() -> pymongo.collection.Collection:
    """
    Return the MongoDB collection used by this app.

    The MongoClient is intentionally created fresh per call so the module
    doesn't hold a long-lived connection that might silently expire.
    For high-traffic apps, replace this with a module-level singleton or a
    connection pool.
    """
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[MONGO_DB][MONGO_COLLECTION]


def save_metadata(records: list) -> bool:
    """
    Insert a list of image-metadata dicts into MongoDB.

    Each record is expected to contain at least:
        query, index, url, filename, static_path

    Returns True on success, False if the insert failed (the app continues
    working even when MongoDB is unavailable — images are still served from
    the filesystem).
    """
    if not records:
        logger.warning("save_metadata called with an empty list — nothing to save.")
        return False

    try:
        col = get_collection()
        result = col.insert_many(records)
        logger.info(
            "Inserted %d metadata records into '%s'.", len(result.inserted_ids), MONGO_COLLECTION
        )
        return True

    except (ConnectionFailure, OperationFailure) as exc:
        logger.error("MongoDB write failed: %s", exc)
        return False
    except Exception as exc:
        logger.exception("Unexpected error while saving to MongoDB: %s", exc)
        return False


def get_all_metadata(query: str = None) -> list:
    """
    Retrieve stored metadata records, optionally filtered by *query*.

    Returns an empty list if MongoDB is unavailable, so callers don't need
    to handle database errors separately.
    """
    try:
        col = get_collection()
        filter_doc = {"query": query} if query else {}
        docs = list(col.find(filter_doc, {"_id": 0}))
        logger.info("Retrieved %d records (query=%r).", len(docs), query)
        return docs
    except Exception as exc:
        logger.error("MongoDB read failed: %s", exc)
        return []
