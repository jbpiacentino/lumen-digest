import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from app.database import SessionLocal
from app.models import Article


def main():
    parser = argparse.ArgumentParser(description="Backfill full_text_format for recent articles.")
    parser.add_argument("--days", type=int, default=3, help="Lookback window in days.")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    with SessionLocal() as session:
        q = session.query(Article).filter(
            and_(
                Article.published_at >= cutoff,
                Article.full_text_source == "trafilatura",
                Article.full_text_format.is_(None),
                Article.full_text.isnot(None),
            )
        )
        updated = q.update({Article.full_text_format: "markdown"}, synchronize_session=False)
        session.commit()

    print(f"Updated {updated} articles.")


if __name__ == "__main__":
    main()
