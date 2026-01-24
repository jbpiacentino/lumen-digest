import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Article
from app.logic.freshrss import get_entries_since
from app.logic.summarizer import summarize_article


SUMMARIZATION_ENABLED = os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true"


def extract_raw_content(entry: dict) -> str:
    title = entry.get("title") or ""
    raw_content = (
        entry.get("content", {}).get("content", "")
        or entry.get("summary", {}).get("content", "")
        or title
    )
    return raw_content


async def build_summary(summary_input: str) -> str:
    if not summary_input:
        return ""
    if SUMMARIZATION_ENABLED:
        return await summarize_article(summary_input[:2000])
    return summary_input[:300] + "..."


async def run(
    days: int | None,
    limit: int,
    apply_changes: bool,
    max_items: int,
    report_missing: int,
):
    if days is None:
        since_ts = 0
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        since_ts = int(cutoff.timestamp())

    entries = await get_entries_since(since_ts, limit=limit, max_items=max_items)
    if not entries:
        print("No entries returned from FreshRSS.")
        return

    updated = 0
    skipped_missing = 0
    skipped_empty = 0

    missing_details = []

    with SessionLocal() as session:
        for entry in entries:
            freshrss_id = str(entry.get("id"))
            if not freshrss_id:
                skipped_missing += 1
                continue

            article = session.execute(
                select(Article).where(Article.freshrss_id == freshrss_id)
            ).scalar_one_or_none()

            if not article:
                skipped_missing += 1
                if report_missing > 0 and len(missing_details) < report_missing:
                    missing_details.append(
                        {
                            "id": freshrss_id,
                            "title": entry.get("title") or "",
                            "url": entry.get("alternate", [{}])[0].get("href"),
                        }
                    )
                continue

            summary_input = extract_raw_content(entry) or article.full_text or article.title or ""
            if not summary_input:
                skipped_empty += 1
                continue

            summary = await build_summary(summary_input)
            updated += 1
            if apply_changes:
                article.summary = summary

        if apply_changes:
            session.commit()

    mode = "APPLIED" if apply_changes else "DRY RUN"
    print(f"{mode}: would update {updated} articles.")
    if skipped_missing:
        print(f"Skipped {skipped_missing} entries with no matching article.")
    if missing_details:
        print("Sample missing entries:")
        for item in missing_details:
            print(f"- {item['id']} | {item['title']} | {item['url']}")
    if skipped_empty:
        print(f"Skipped {skipped_empty} entries with empty content.")


def main():
    parser = argparse.ArgumentParser(description="Backfill summaries using FreshRSS raw content.")
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Lookback window in days. Use --all to backfill everything.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all entries available in FreshRSS.",
    )
    parser.add_argument(
        "--report-missing",
        type=int,
        default=0,
        help="Print up to N missing FreshRSS entries.",
    )
    parser.add_argument("--limit", type=int, default=200, help="FreshRSS page size.")
    parser.add_argument("--max-items", type=int, default=2000, help="Maximum items to fetch.")
    parser.add_argument("--apply", action="store_true", help="Apply updates to the database.")
    args = parser.parse_args()

    days = None if args.all else args.days
    asyncio.run(run(days, args.limit, args.apply, args.max_items, args.report_missing))


if __name__ == "__main__":
    main()
