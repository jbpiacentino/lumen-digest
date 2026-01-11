import datetime
import time
start_time = time.time()

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import json

from .database import engine, Base, SessionLocal # Import your DB setup
from .models import Article
from sqlalchemy.dialects.postgresql import insert # For idempotency (no duplicates)

from typing import List, Optional
import logging
from dotenv import load_dotenv

# Import our logic modules
from .logic.freshrss import get_unread_entries
from .logic.summarizer import summarize_article
from .logic.classifier import classifier_engine

# Load environment variables from .env file
load_dotenv()

# Set the logging level based on an environment variable, defaulting to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
# Helper to convert string env var to boolean
SUMMARIZATION_ENABLED = os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true"

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


@app.on_event("startup")
async def startup_event():
    print("DEBUG: Startup event triggered - App is ready")

@app.get("/")
async def root():
    return {"status": "online", "message": "Lumen Digest AI Backend", "LOG_LEVEL": LOG_LEVEL, "summarization_active": SUMMARIZATION_ENABLED}

@app.get("/digest/sync")
async def sync_and_classify(limit: int = Query(default=10, le=50)):
    db = SessionLocal()
    try:        
        # 1. Fetch from FreshRSS (GReader API)
        to_process = await get_unread_entries()
        logger.info(f"to_process len = {len(to_process)} .")
        processed_items = []

        for entry in to_process:
            # Extract content (prioritize content over summary)
            title = entry.get("title", "No Title")
            raw_content = entry.get("content", {}).get("content", "") or \
                          entry.get("summary", {}).get("content", "") or \
                          title
            raw_pub_date = entry.get("published") 
            try:
                # Convert timestamp to datetime object
                pub_date = datetime.datetime.fromtimestamp(int(raw_pub_date), tz=datetime.timezone.utc)
            except (ValueError, TypeError):
                # Fallback to now if date is missing/malformed
                pub_date = datetime.datetime.now(datetime.timezone.utc)
            
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
            category_id = classifier_engine.classify_text(classification_text)
            
            logger.debug(f"Article: {title[:40]}... -> Category: {category_id}")

            # Prepare the data dictionary
            article_data = {
                "freshrss_id": str(entry.get("id")), # This provides our uniqueness
                "title": entry.get("title"),
                "url": entry.get("alternate", [{}])[0].get("href"),
                "summary": entry.get("summary", {}).get("content", ""),
                "category_id": category_id,
                "published_at": pub_date
            }

            # Insert into DB
            # Use 'on_conflict_do_nothing' so you don't get errors if you sync the same item twice
            print("inserting ", article_data["title"])
            stmt = insert(Article).values(**article_data).on_conflict_do_nothing(
                index_elements=['freshrss_id'] # Assumes you have a unique constraint on this
            )
            db.execute(stmt)
            db.commit() 

            # processed_items.append(article_data)
            processed_items.append({
                "id": entry.get("id"),
                "title": title,
                "url": entry.get("alternate", [{}])[0].get("href"),
                "category_id": category_id,
                "summary": summary,
                "published_at": entry.get("published")
            })

        return {
            "count": len(processed_items),
            "articles": processed_items
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Sync failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-classifier")
async def test_classifier(text: str):
    """
    Utility endpoint to test how the DNA engine categorizes a specific string.
    """
    category = classifier_engine.classify_text(text)
    return {
        "input": text,
        "assigned_category": category
    }

@app.get("/taxonomy/reload")
async def reload_taxonomy():
    """
    Call this if you update your taxonomy.json while the server is running.
    """
    classifier_engine.load_taxonomy()
    return {"message": "Taxonomy centroids recalculated successfully."}

@app.get("/digest/categories")
async def get_categories(lang: str = "en"):
    """
    Returns taxonomy labels. Usage: /digest/categories?lang=en
    """
    return classifier_engine.get_taxonomy_labels(lang=lang)