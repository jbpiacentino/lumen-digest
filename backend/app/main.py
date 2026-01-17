from datetime import datetime, timezone, timedelta
import time
import asyncio
start_time = time.time()

import os
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
import json

from .database import engine, Base, SessionLocal, get_db # Import your DB setup
from .models import Article
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert # For idempotency (no duplicates)

from typing import List, Optional
import logging
from dotenv import load_dotenv
from pydantic import BaseModel

# Import our logic modules
from .logic.freshrss import get_unread_entries, mark_entries_read
from .logic.summarizer import summarize_article
from .logic.classifier import get_classifier_engine

# Load environment variables from .env file
load_dotenv()


LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
SUMMARIZATION_ENABLED = os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
POLL_ENABLED = os.getenv("POLL_ENABLED", "true").lower() == "true"

SYNC_LIMIT = int(os.getenv("FRESHRSS_SYNC_LIMIT", "200"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(levelname)s:     %(name)s - %(message)s",
)

# This ensures the specific logger for this file is also set to DEBUG
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# This creates the table if it doesn't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lumen Digest API.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers
)

class ClassifyBatchRequest(BaseModel):
    texts: List[str]
    threshold: float = 0.36
    margin_threshold: float = 0.07
    min_len: int = 30
    low_bucket: str = "other"

class ClassifyRequest(BaseModel):
    text: str
    threshold: float = 0.36
    margin_threshold: float = 0.07
    min_len: int = 30
    low_bucket: str = "other"


async def sync_entries(limit: int, db: Session):
    # 1. Fetch from FreshRSS (GReader API)
    to_process = await get_unread_entries(limit=limit)
    logger.info(f"to_process len = {len(to_process)} .")
    processed_ids = []

    for entry in to_process[:limit]:
        # Extract content (prioritize content over summary)
        title = entry.get("title", "No Title")
        raw_content = entry.get("content", {}).get("content", "") or \
                      entry.get("summary", {}).get("content", "") or \
                      title
        raw_pub_date = entry.get("published") 
        try:
            # Convert timestamp to datetime object
            # Remove the "datetime." prefix before timezone
            pub_date = datetime.fromtimestamp(int(raw_pub_date), tz=timezone.utc)
        except (ValueError, TypeError):
            # Fallback to now if date is missing/malformed
            pub_date = datetime.now(datetime.timezone.utc)
        
        # Generate AI Summary
        if SUMMARIZATION_ENABLED:
            logger.debug(f"Summarizing: {title}")
            summary = await summarize_article(raw_content[:2000])
        else:
            # If disabled, we just use a snippet of the raw content for the UI
            summary = raw_content[:300] + "..."

        # Classify Category (Local ML)
        # If AI is off, we MUST use the title + raw_content to classify, 
        # otherwise the classifier doesn't have enough data.
        classification_text = f"{title}: {raw_content[:1000]}"
        category_id = get_classifier_engine().classify_text(classification_text)
        
        logger.debug(f"Article: {title[:40]}... -> Category: {category_id}")

        # Prepare the data dictionary
        article_data = {
            "freshrss_id": str(entry.get("id")), # This provides our uniqueness
            "title": entry.get("title"),
            "url": entry.get("alternate", [{}])[0].get("href"),
            "summary": summary,
            "category_id": category_id,
            "published_at": pub_date
        }

        # Insert into DB
        # Use 'on_conflict_do_nothing' so we don't get errors if we sync the same item twice
        stmt = insert(Article).values(**article_data).on_conflict_do_nothing(
            index_elements=['freshrss_id'] # Assumes you have a unique constraint on this
        )
        db.execute(stmt)
        db.commit()
        entry_id = entry.get("id")
        if entry_id:
            processed_ids.append(str(entry_id))

    await mark_entries_read(processed_ids)

async def polling_loop():
    logger.info("FreshRSS polling loop started.")
    while True:
        try:
            with SessionLocal() as db:
                await sync_entries(limit=SYNC_LIMIT, db=db)
        except Exception as e:
            logger.error(f"Background polling failed: {str(e)}", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

@app.on_event("startup")
async def startup_event():
    print("DEBUG: Startup event triggered - App is ready")
    if POLL_ENABLED:
        app.state.polling_task = asyncio.create_task(polling_loop())
        logger.info("FreshRSS polling enabled.")

@app.on_event("shutdown")
async def shutdown_event():
    polling_task = getattr(app.state, "polling_task", None)
    if polling_task:
        polling_task.cancel()

@app.get("/")
async def root():
    return {"status": "online", "message": "Lumen Digest AI Backend", "LOG_LEVEL": LOG_LEVEL, "summarization_active": SUMMARIZATION_ENABLED}

@app.get("/articles")
def get_articles(
    days: int = Query(default=0, description="Number of days to look back (0 for all)"),
    category_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of classified articles from the internal database.

    This is the primary endpoint for the frontend UI. It does not trigger new 
    external fetches; instead, it queries already-processed data.

    Args:
        days (int): The look-back window in days. Defaults to 1 (last 24 hours).
        category_id (Optional[str]): If provided, filters articles by a specific 
            category (e.g., 'tech', 'finance').
        db (Session): SQLAlchemy database session.

    Returns:
        List[Article]: A JSON array of article objects sorted by newest first.
    """
    # Start the query
    query = db.query(Article)

    if days and days > 0:
        # Calculate the cutoff time (default 24h ago)
        # Using timezone-aware UTC if your DB stores it that way
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(Article.published_at >= cutoff)
    
    # Optional: Filter by category if provided
    if category_id:
        query = query.filter(Article.category_id == category_id)
        
    # Sort by newest first
    articles = query.order_by(Article.published_at.desc()).all()
    
    return articles

@app.get("/digest/sync")
async def sync_and_classify(limit: int = Query(default=SYNC_LIMIT, le=SYNC_LIMIT), db: Session = Depends(get_db)):
 
    """
    Worker endpoint to synchronize FreshRSS entries with the local database.

    This function performs the heavy lifting:
    1. Fetches the latest unread headers from the FreshRSS (GReader) API.
    2. Filters for items not yet present in the local database.
    3. Uses LLM analysis to assign a `category_id` based on title and snippet.
    4. Persists the enriched articles to PostgreSQL.

    Args:
        limit (int): Maximum number of new articles to process in this batch 
            to manage API costs and latency.
        db (Session): SQLAlchemy database session.

    Returns:
        dict: A status message indicating how many articles were processed.
    """
    try:        
        await sync_entries(limit=limit, db=db)

        return {"status": "success", "message": f"Synced up to {limit} articles"}

    except Exception as e:
        db.rollback()
        logger.error(f"Sync failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-classifier")
async def test_classifier(text: str):
    """
    Utility endpoint to test how the DNA engine categorizes a specific string.
    """
    category = get_classifier_engine().classify_text(text)
    return {
        "input": text,
        "assigned_category": category
    }

@app.post("/classify")
async def classify(payload: ClassifyRequest):
    result = get_classifier_engine().classify_text_with_scores(
        payload.text,
        threshold=payload.threshold,
        margin_threshold=payload.margin_threshold,
        min_len=payload.min_len,
        low_bucket=payload.low_bucket,
    )
    return {"result": result}

@app.post("/classify/batch")
async def classify_batch(payload: ClassifyBatchRequest):
    clf = get_classifier_engine()
    results = [
        clf.classify_text_with_scores(
            text,
            threshold=payload.threshold,
            margin_threshold=payload.margin_threshold,
            min_len=payload.min_len,
            low_bucket=payload.low_bucket,
        )
        for text in payload.texts
    ]
    return {"results": results}

@app.get("/taxonomy/reload")
async def reload_taxonomy():
    """
    Call this if you update your taxonomy.json while the server is running.
    """
    get_classifier_engine().load_taxonomy()
    return {"message": "Taxonomy centroids recalculated successfully."}

@app.get("/digest/categories")
async def get_categories(lang: str = "en"):
    """
    Returns taxonomy labels. Usage: /digest/categories?lang=en
    """
    return get_classifier_engine().get_taxonomy_labels(lang=lang)

@app.get("/digest/category-tree")
async def get_category_tree(lang: str = "en"):
    """
    Returns taxonomy tree. Usage: /digest/category-tree?lang=en
    """
    return get_classifier_engine().get_taxonomy_tree(lang=lang)
