import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, or_, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.logic.classifier import get_classifier_engine  # noqa: E402
from app.models import Article  # noqa: E402


def iter_batches(query, batch_size: int):
    last_id = 0
    while True:
        batch = query.filter(Article.id > last_id).limit(batch_size).all()
        if not batch:
            break
        last_id = batch[-1].id
        yield batch


def main():
    p = argparse.ArgumentParser(
        description="Re-run news classifier on the articles table and update category_id."
    )
    p.add_argument(
        "--db",
        default=os.getenv("DATABASE_URL"),
        help="SQLAlchemy DB URL (or set DATABASE_URL).",
    )
    p.add_argument("--taxonomy", required=True, help="Path to taxonomy JSON.")
    p.add_argument(
        "--model",
        default="paraphrase-multilingual-mpnet-base-v2",
        help="SentenceTransformer model name.",
    )
    p.add_argument(
        "--centroids-cache", default=None, help="Optional path for centroid cache (torch.save)."
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.38,
        help="Confidence threshold for accepting category.",
    )
    p.add_argument(
        "--min-len",
        type=int,
        default=30,
        help="Min cleaned text length, else 'other' + needs_review.",
    )
    p.add_argument("--batch-size", type=int, default=500, help="Rows per commit.")
    p.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = no limit).")
    p.add_argument(
        "--only-uncategorized",
        action="store_true",
        help="Process only rows where category_id is NULL/'uncategorized'/'other'.",
    )
    p.add_argument(
        "--reclassify-all",
        action="store_true",
        help="Reclassify everything (including already classified).",
    )
    p.add_argument(
        "--where",
        default=None,
        help='Optional SQL WHERE fragment, e.g. "source = \'BFMTV\'" (advanced).',
    )
    p.add_argument("--dry-run", action="store_true", help="Do not write updates; only print stats.")
    p.add_argument(
        "--update-unchanged",
        action="store_true",
        help="Write even if category_id/confidence would not change.",
    )
    p.add_argument(
        "--print-samples",
        type=int,
        default=10,
        help="Print N sample changes (0 to disable).",
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print progress every N records (0 to disable).",
    )

    args = p.parse_args()

    if not args.db:
        raise SystemExit("Missing DB URL. Provide --db or set DATABASE_URL.")
    if args.only_uncategorized and args.reclassify_all:
        raise SystemExit("Choose only one of --only-uncategorized or --reclassify-all.")
    if not args.only_uncategorized and not args.reclassify_all:
        args.only_uncategorized = True

    engine = create_engine(args.db)
    Session = sessionmaker(bind=engine)

   

    classifier = get_classifier_engine(
        taxonomy_path=args.taxonomy,
        model_name=args.model,
        centroids_cache=args.centroids_cache,
    )
    if not classifier.categories:
        raise SystemExit("No categories loaded from taxonomy.")

    total_seen = 0
    total_updated = 0
    total_skipped = 0
    samples_printed = 0

    with Session() as session:
        query = session.query(Article).order_by(Article.id.asc())
        if args.only_uncategorized:
            query = query.filter(
                or_(
                    Article.category_id.is_(None),
                    Article.category_id.in_(["uncategorized", "other"]),
                )
            )
        if args.where:
            query = query.filter(text(args.where))

        for batch in iter_batches(query, args.batch_size):
            for article in batch:
                total_seen += 1
                if args.limit and total_seen > args.limit:
                    break

                title = article.title or ""
                summary = article.summary or ""
                classification_text = f"{title}: {summary}"

                result = classifier.classify_text_with_scores(
                    classification_text, threshold=args.threshold, min_len=args.min_len
                )

                new_category = result["category_id"]
                new_conf = result["confidence"]
                changed = (
                    article.category_id != new_category
                    or (article.confidence or 0.0) != new_conf
                )

                if not args.update_unchanged and not changed:
                    total_skipped += 1
                    continue

                if args.print_samples and samples_printed < args.print_samples:
                    print(
                        f"id={article.id} {article.category_id}->{new_category} "
                        f"conf={new_conf:.4f}"
                    )
                    samples_printed += 1

                if not args.dry_run:
                    article.category_id = new_category
                    article.confidence = new_conf
                    article.runner_up_confidence = result["runner_up_confidence"]
                    article.margin = result["margin"]
                    article.needs_review = result["needs_review"]
                    article.reason = result["reason"]
                total_updated += 1
                if args.progress_every and total_seen % args.progress_every == 0:
                    print(
                        f"Progress: seen={total_seen} updated={total_updated} skipped={total_skipped}"
                    )

            if args.dry_run:
                session.rollback()
            else:
                session.commit()

            if args.limit and total_seen >= args.limit:
                break

    print(
        f"Done. seen={total_seen} updated={total_updated} skipped={total_skipped} "
        f"dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
