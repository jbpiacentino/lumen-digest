import os
import argparse
from typing import Dict, Any, Optional, List, Tuple

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from langdetect import DetectorFactory, LangDetectException, detect


def to_float(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def to_bool(x: Any) -> Optional[bool]:
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in ("true", "t", "1", "yes", "y"):
        return True
    if s in ("false", "f", "0", "no", "n"):
        return False
    return None

def float_changed(a: Any, b: Any, eps: float) -> bool:
    return abs(to_float(a) - to_float(b)) > eps


DetectorFactory.seed = 0

def detect_language(text_value: str, default: str = "en") -> str:
    if not text_value or not text_value.strip():
        return default
    try:
        return detect(text_value)
    except LangDetectException:
        return default


def main():
    p = argparse.ArgumentParser("Reclassify lumen-digest articles in DB")

    p.add_argument("--db", required=True, help="SQLAlchemy DB URL")
    p.add_argument("--classifier-url", default=os.getenv("CLASSIFIER_URL", "http://localhost:8000"),
                   help="Base URL for the classifier API (e.g. http://localhost:8000).")
    p.add_argument("--classifier-timeout", type=float, default=30.0,
                   help="HTTP timeout in seconds for classifier requests.")

    p.add_argument("--threshold", type=float, default=0.36)
    p.add_argument("--margin", type=float, default=0.07)
    p.add_argument("--min-len", type=int, default=30)
    p.add_argument("--low-bucket", default="other")

    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--classify-batch-size", type=int, default=100,
                   help="Batch size for classifier API calls.")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--classify-max-chars", type=int, default=3000)

    p.add_argument("--reclassify-all", action="store_true")
    p.add_argument("--only-uncategorized", action="store_true")
    p.add_argument("--where", default=None)

    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--print-samples", type=int, default=20)
    p.add_argument("--eps", type=float, default=1e-6)

    p.add_argument("--change-scope", choices=["category", "category_review", "all"], default="category_review")
    p.add_argument("--write-scope", choices=["category", "category_review", "all"], default="category_review")
    p.add_argument("--backfill-language", action="store_true",
                   help="Detect and store article language in the language column.")
    p.add_argument("--force-language", action="store_true",
                   help="Update language even if a value already exists.")
    p.add_argument("--language-only", action="store_true",
                   help="Only backfill language, skip classifier calls and category updates.")

    args = p.parse_args()

    if args.language_only:
        args.backfill_language = True

    classifier_url = args.classifier_url.rstrip("/")
    session_http = requests.Session()

    base_sql = """
      SELECT
        id, category_id, confidence, needs_review, reason,
        runner_up_confidence, margin, title, summary, full_text, language
      FROM articles
    """

    conditions = []
    if args.where:
        conditions.append(f"({args.where})")

    if args.only_uncategorized and not args.reclassify_all:
        conditions.append("(category_id IN ('uncategorized','other'))")
    elif not args.reclassify_all:
        conditions.append("(category_id = 'uncategorized')")

    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    limit_sql = f" LIMIT {args.limit}" if args.limit and args.limit > 0 else ""
    select_sql = base_sql + where_sql + " ORDER BY id" + limit_sql

    update_templates = {
        "category": """
          UPDATE articles SET category_id = :category_id WHERE id = :id
        """,
        "category_review": """
          UPDATE articles
          SET category_id = :category_id,
              needs_review = :needs_review,
              reason = :reason
          WHERE id = :id
        """,
        "all": """
          UPDATE articles
          SET category_id = :category_id,
              confidence = :confidence,
              needs_review = :needs_review,
              reason = :reason,
              runner_up_confidence = :runner_up_confidence,
              margin = :margin
          WHERE id = :id
        """,
    }
    update_sql = text(update_templates[args.write_scope])
    language_update_sql = text("UPDATE articles SET language = :language WHERE id = :id")

    def is_changed(old: dict, new: dict) -> bool:
        if args.change_scope == "category":
            return old["category_id"] != new["category_id"]

        if args.change_scope == "category_review":
            return (
                old["category_id"] != new["category_id"]
                or (to_bool(old["needs_review"]) != new["needs_review"])
                or ((old["reason"] or "") != (new["reason"] or ""))
            )

        return (
            old["category_id"] != new["category_id"]
            or float_changed(old["confidence"], new["confidence"], args.eps)
            or (to_bool(old["needs_review"]) != new["needs_review"])
            or ((old["reason"] or "") != (new["reason"] or ""))
            or float_changed(old["runner_up_confidence"], new["runner_up_confidence"], args.eps)
            or float_changed(old["margin"], new["margin"], args.eps)
        )

    def classify_batch(texts: List[str]) -> List[Dict[str, Any]]:
        if not texts:
            return []
        payload = {
            "texts": texts,
            "threshold": args.threshold,
            "margin_threshold": args.margin,
            "min_len": args.min_len,
            "low_bucket": args.low_bucket,
        }
        resp = session_http.post(
            f"{classifier_url}/classify/batch",
            json=payload,
            timeout=args.classifier_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results")
        if results is None or len(results) != len(texts):
            raise RuntimeError("Classifier response missing or mismatched results.")
        return results

    processed = 0
    would_change = 0
    updated = 0
    language_updated = 0
    dist: Dict[str, int] = {}
    samples: List[Tuple[int, str, str, float, float, str, str]] = []

    engine = create_engine(args.db, future=True)
    with Session(engine) as session:
        rows = session.execute(text(select_sql)).mappings()

        pending = 0
        batch: List[Tuple[dict, str]] = []

        def process_batch(items: List[Tuple[dict, str]]) -> None:
            nonlocal pending, would_change, updated, language_updated
            texts = [raw for _, raw in items]
            results = [] if args.language_only else classify_batch(texts)

            for idx, (r, raw_text) in enumerate(items):
                if not args.language_only:
                    out = results[idx]
                    dist[out["category_id"]] = dist.get(out["category_id"], 0) + 1

                    old = {
                        "category_id": r["category_id"],
                        "confidence": r["confidence"],
                        "needs_review": r["needs_review"],
                        "reason": r["reason"],
                        "runner_up_confidence": r["runner_up_confidence"],
                        "margin": r["margin"],
                    }

                    changed = is_changed(old, out)
                    if changed:
                        would_change += 1
                        if args.print_samples and len(samples) < args.print_samples:
                            samples.append((
                                r["id"],
                                old["category_id"],
                                out["category_id"],
                                to_float(old["confidence"]),
                                to_float(out["confidence"]),
                                str(old["reason"] or ""),
                                str(out["reason"] or ""),
                            ))

                    if not args.dry_run and changed:
                        session.execute(update_sql, {"id": r["id"], **out})
                        updated += 1
                        pending += 1

                if args.backfill_language:
                    existing_lang = (r.get("language") or "").strip()
                    if args.force_language or not existing_lang:
                        detected_lang = detect_language(raw_text, default="en")
                        if args.dry_run:
                            language_updated += 1
                        else:
                            session.execute(language_update_sql, {"id": r["id"], "language": detected_lang})
                            language_updated += 1
                            pending += 1

                if pending >= args.batch_size:
                    session.commit()
                    pending = 0

        for r in rows:
            processed += 1
            body = r["full_text"] or r["summary"] or ""
            raw = (r["title"] or "") + "\n\n" + body
            raw = raw[: args.classify_max_chars + 2 + len(r["title"] or "")]
            batch.append((r, raw))
            if len(batch) >= args.classify_batch_size:
                process_batch(batch)
                batch = []

        if batch:
            process_batch(batch)

        if not args.dry_run and pending:
            session.commit()

    print("\n=== Reclassify Report ===")
    print(f"Classifier URL: {classifier_url}")
    print(f"Processed: {processed}")
    print(f"Would change ({args.change_scope}): {would_change}")
    print(f"Updated: {0 if args.dry_run else updated}")
    if args.backfill_language:
        print(f"Language updated: {language_updated} (dry-run count if applicable)")

    print("\nNew assignment distribution:")
    for k in sorted(dist.keys()):
        print(f"  {k}: {dist[k]}")

    if samples:
        print("\nSample changes:")
        for (id_, old_cat, new_cat, old_conf, new_conf, old_reason, new_reason) in samples:
            print(f"  id={id_}  {old_cat} ({old_conf:.3f}, {old_reason}) -> {new_cat} ({new_conf:.3f}, {new_reason})")

    if args.dry_run:
        print("\nDry-run: no DB writes performed.")


if __name__ == "__main__":
    main()
