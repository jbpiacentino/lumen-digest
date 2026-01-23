from datetime import datetime, timezone, timedelta
import time
import asyncio
start_time = time.time()

import os
import httpx
import trafilatura
from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
import json

from .database import engine, Base, SessionLocal, get_db # Import your DB setup
from .models import Article, User
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert # For idempotency (no duplicates)
from sqlalchemy import or_

from typing import List, Optional
import logging
from dotenv import load_dotenv
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError

# Import our logic modules
from .logic.freshrss import get_unread_entries, mark_entries_read
from .logic.summarizer import summarize_article
from .logic.classifier import get_classifier_engine
from .logic.lang import detect_language

# Load environment variables from .env file
load_dotenv()


LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
SUMMARIZATION_ENABLED = os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
POLL_ENABLED = os.getenv("POLL_ENABLED", "true").lower() == "true"
FULLTEXT_ENABLED = os.getenv("FULLTEXT_ENABLED", "true").lower() == "true"
FULLTEXT_TIMEOUT_SECONDS = float(os.getenv("FULLTEXT_TIMEOUT_SECONDS", "10"))
FULLTEXT_MAX_CHARS = int(os.getenv("FULLTEXT_MAX_CHARS", "20000"))
FULLTEXT_CLASSIFY_MAX_CHARS = int(os.getenv("FULLTEXT_CLASSIFY_MAX_CHARS", "3000"))
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_SECRET = os.getenv("AUTH_SECRET", "change-me")
AUTH_ALGORITHM = "HS256"
AUTH_ACCESS_TOKEN_MINUTES = int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "1440"))

SYNC_LIMIT = int(os.getenv("FRESHRSS_SYNC_LIMIT", "200"))

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

class ReviewUpdateRequest(BaseModel):
    review_status: Optional[str] = None
    override_category_id: Optional[str] = None
    review_flags: Optional[List[str]] = None
    review_note: Optional[str] = None

class ReclassifyRequest(BaseModel):
    threshold: float = 0.36
    margin_threshold: float = 0.07
    min_len: int = 30
    low_bucket: str = "other"
    top_k: int = 5
    apply: bool = True


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def validate_password(password: str) -> None:
    if not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password must be 72 bytes or fewer")


def hash_password(password: str) -> str:
    validate_password(password)
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=AUTH_ACCESS_TOKEN_MINUTES)
    payload = {"sub": str(user.id), "email": user.email, "exp": expire}
    return jwt.encode(payload, AUTH_SECRET, algorithm=AUTH_ALGORITHM)


def get_user_from_token(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, AUTH_SECRET, algorithms=[AUTH_ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
) -> Optional[User]:
    if not AUTH_ENABLED:
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    return get_user_from_token(token, db)


def extract_full_text_from_html(html: str) -> str:
    if not html:
        return ""
    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_formatting=True,
        include_images=True,
        include_comments=False,
        include_tables=True,
        include_links=True,
    )
    if not extracted:
        return ""
    return extracted.strip()[:FULLTEXT_MAX_CHARS]


async def extract_full_text(url: str) -> str:
    if not url:
        return ""
    headers = {
        "User-Agent": "LumenDigestBot/1.0 (+https://github.com/)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, headers=headers, timeout=FULLTEXT_TIMEOUT_SECONDS)
        resp.raise_for_status()
        html = resp.text
    return extract_full_text_from_html(html)


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
        url = entry.get("alternate", [{}])[0].get("href")
        full_text = ""
        full_text_source = None
        full_text_format = None
        if FULLTEXT_ENABLED and url:
            try:
                full_text = await extract_full_text(url)
                if full_text:
                    full_text_source = "trafilatura"
                    full_text_format = "markdown"
            except Exception as exc:
                logger.warning(f"Full-text extraction failed for {url}: {exc}")
        raw_pub_date = entry.get("published") 
        try:
            # Convert timestamp to datetime object
            # Remove the "datetime." prefix before timezone
            pub_date = datetime.fromtimestamp(int(raw_pub_date), tz=timezone.utc)
        except (ValueError, TypeError):
            # Fallback to now if date is missing/malformed
            pub_date = datetime.now(datetime.timezone.utc)
        
        # Generate AI Summary
        summary_input = full_text or raw_content
        if SUMMARIZATION_ENABLED:
            logger.debug(f"Summarizing: {title}")
            summary = await summarize_article(summary_input[:2000])
        else:
            # If disabled, we just use a snippet of the raw content for the UI
            summary = summary_input[:300] + "..."

        # Classify Category (Local ML)
        # If AI is off, we MUST use the title + raw_content to classify,
        # otherwise the classifier does not have enough data.
        classification_text = f"{title}: {summary_input[:FULLTEXT_CLASSIFY_MAX_CHARS]}"
        detected_lang = detect_language(classification_text, default="en")
        classify_result = get_classifier_engine().classify_text_with_scores(
            classification_text
        )
        category_id = classify_result["category_id"]

        logger.debug(f"Article: {title[:40]}... -> Category: {category_id}")

        # Prepare the data dictionary
        origin = entry.get("origin") or entry.get("source") or {}
        source_name = origin.get("title") or entry.get("author")
        article_data = {
            "freshrss_id": str(entry.get("id")), # This provides our uniqueness
            "title": entry.get("title"),
            "url": url,
            "summary": summary,
            "full_text": full_text or None,
            "full_text_source": full_text_source,
            "full_text_format": full_text_format,
            "category_id": category_id,
            "confidence": classify_result["confidence"],
            "needs_review": classify_result["needs_review"],
            "reason": classify_result["reason"],
            "runner_up_confidence": classify_result["runner_up_confidence"],
            "margin": classify_result["margin"],
            "language": detected_lang,
            "source": source_name,
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

@app.post("/auth/signup", response_model=AuthResponse)
def signup(data: AuthRequest, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    if not email:
        raise HTTPException(status_code=400, detail="Email and password required")
    validate_password(data.password)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user)
    return AuthResponse(access_token=token, user={"id": user.id, "email": user.email})


@app.post("/auth/login", response_model=AuthResponse)
def login(data: AuthRequest, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    if not email:
        raise HTTPException(status_code=400, detail="Email and password required")
    validate_password(data.password)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return AuthResponse(access_token=token, user={"id": user.id, "email": user.email})

@app.get("/")
async def root():
    return {"status": "online", "message": "Lumen Digest AI Backend", "LOG_LEVEL": LOG_LEVEL, "summarization_active": SUMMARIZATION_ENABLED}

@app.get("/articles")
def get_articles(
    days: int = Query(default=0, description="Number of days to look back (0 for all)"),
    hours: int = Query(default=0, description="Number of hours to look back (0 for all)"),
    category_ids: Optional[List[str]] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=0),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_user)
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

    if hours and hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.filter(Article.published_at >= cutoff)
    elif days and days > 0:
        # Calculate the cutoff time (default 24h ago)
        # Using timezone-aware UTC if your DB stores it that way
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(Article.published_at >= cutoff)
    
    # Optional: Filter by category if provided
    ids = [i.strip() for i in (category_ids or []) if i and i.strip()]

    if ids:
        if "uncategorized" in ids:
            query = query.filter(
                or_(
                    Article.category_id.in_(ids),
                    Article.category_id.is_(None),
                )
            )
        else:
            query = query.filter(Article.category_id.in_(ids))
        
    total = query.order_by(None).count()

    # Sort by newest first
    query = query.order_by(Article.published_at.desc())
    if page_size > 0:
        query = query.offset((page - 1) * page_size).limit(page_size)
    articles = query.all()
    
    return {
        "items": articles,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.patch("/articles/{article_id}/review")
def update_article_review(
    article_id: int,
    payload: ReviewUpdateRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_user),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    data = payload.dict(exclude_unset=True)
    if "review_status" in data:
        article.review_status = data["review_status"]
    if "override_category_id" in data:
        article.override_category_id = data["override_category_id"]
    if "review_flags" in data:
        article.review_flags = data["review_flags"]
    if "review_note" in data:
        article.review_note = data["review_note"]

    db.commit()
    db.refresh(article)
    return jsonable_encoder(article)

@app.post("/articles/{article_id}/refetch-full-text")
async def refetch_article_full_text(
    article_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_user),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if not article.url:
        raise HTTPException(status_code=400, detail="Article missing URL")

    try:
        full_text = await extract_full_text(article.url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Full-text extraction failed: {exc}")

    article.full_text = full_text or None
    article.full_text_source = "trafilatura" if full_text else None
    article.full_text_format = "markdown" if full_text else None
    db.commit()
    db.refresh(article)
    return jsonable_encoder(article)

@app.post("/articles/{article_id}/reclassify")
def reclassify_article(
    article_id: int,
    payload: ReclassifyRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_user),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    raw_text = article.title or ""
    if article.summary:
        raw_text = f"{raw_text}: {article.summary}"

    classifier = get_classifier_engine()
    cleaned_text, scores = classifier.score_text(raw_text, min_len=payload.min_len)
    result = classifier.classify_text_with_scores(
        raw_text,
        threshold=payload.threshold,
        margin_threshold=payload.margin_threshold,
        min_len=payload.min_len,
        low_bucket=payload.low_bucket,
    )

    if payload.apply:
        article.category_id = result["category_id"]
        article.confidence = result["confidence"]
        article.needs_review = result["needs_review"]
        article.reason = result["reason"]
        article.runner_up_confidence = result["runner_up_confidence"]
        article.margin = result["margin"]
        db.commit()
        db.refresh(article)

    top_k = scores[: max(payload.top_k, 0)] if payload.top_k else []

    return {
        "article": jsonable_encoder(article),
        "applied": payload.apply,
        "result": result,
        "debug": {
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "top_k": top_k,
        },
    }

@app.get("/digest/sync")
async def sync_and_classify(
    limit: int = Query(default=SYNC_LIMIT, le=SYNC_LIMIT),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(require_user),
):
 
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
async def test_classifier(text: str, user: Optional[User] = Depends(require_user)):
    """
    Utility endpoint to test how the DNA engine categorizes a specific string.
    """
    category = get_classifier_engine().classify_text(text)
    return {
        "input": text,
        "assigned_category": category
    }

@app.post("/classify")
async def classify(payload: ClassifyRequest, user: Optional[User] = Depends(require_user)):
    result = get_classifier_engine().classify_text_with_scores(
        payload.text,
        threshold=payload.threshold,
        margin_threshold=payload.margin_threshold,
        min_len=payload.min_len,
        low_bucket=payload.low_bucket,
    )
    return {"result": result}

@app.post("/classify/batch")
async def classify_batch(payload: ClassifyBatchRequest, user: Optional[User] = Depends(require_user)):
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
async def reload_taxonomy(user: Optional[User] = Depends(require_user)):
    """
    Call this if you update your taxonomy.json while the server is running.
    """
    get_classifier_engine().load_taxonomy()
    return {"message": "Taxonomy centroids recalculated successfully."}

@app.get("/digest/taxonomy")
async def get_taxonomy(lang: str = "en", user: Optional[User] = Depends(require_user)):
    """
    Returns taxonomy labels and tree. Usage: /digest/taxonomy?lang=en
    """
    return get_classifier_engine().get_taxonomy(lang=lang)
