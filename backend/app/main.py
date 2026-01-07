print("DEBUG: Script started")
import time
start_time = time.time()

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
print(f"DEBUG: FastAPI imported in {time.time() - start_time:.2f}s")

from typing import List, Optional
import logging
from dotenv import load_dotenv

# Import our logic modules
from .logic.freshrss import get_unread_entries
print(f"DEBUG: freshrss imported in {time.time() - start_time:.2f}s")
from .logic.summarizer import summarize_article
print(f"DEBUG: summarizer imported in {time.time() - start_time:.2f}s")
from .logic.classifier import classifier_engine
print(f"DEBUG: classifier imported in {time.time() - start_time:.2f}s")

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
    try:        
        # 1. Fetch from FreshRSS (GReader API)
        raw_articles = await get_unread_entries()
        logger.info(f"Got {len(raw_articles)} raw articles.")

        # Limit processing for performance/cost control
        # to_process = raw_articles[:limit]
        to_process = raw_articles
        processed_items = []

        logger.info(f"Syncing {len(to_process)} articles. AI Summaries: {SUMMARIZATION_ENABLED}")

        for entry in to_process:
            # Extract content (prioritize content over summary)
            title = entry.get("title", "No Title")
            raw_content = entry.get("content", {}).get("content", "") or \
                          entry.get("summary", {}).get("content", "") or \
                          title

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
            
            category = classifier_engine.classify_text(classification_text)
            
            logger.debug(f"Article: {title[:40]}... -> Category: {category}")

            processed_items.append({
                "id": entry.get("id"),
                "title": title,
                "url": entry.get("alternate", [{}])[0].get("href"),
                "category": category,
                "summary": summary,
                "published_at": entry.get("published")
            })

        return {
            "count": len(processed_items),
            "articles": processed_items
        }

    except Exception as e:
        # import traceback
        # traceback.print_exc() # This prints the full 'map' of the error
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
