import argparse
import glob
import os
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def _get_sld(host: str) -> str:
    try:
        from publicsuffix2 import get_sld
    except Exception:
        get_sld = None
    if get_sld:
        return get_sld(host) or host
    parts = host.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host


def normalize_host(url: str) -> Optional[str]:
    if not url:
        return None
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    host = _get_sld(host)
    return host or None


def host_variants(url: str) -> list:
    if not url:
        return []
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return []
    host = host.lower()
    variants = []
    if host:
        variants.append(host)
    if host.startswith("www."):
        variants.append(host[4:])
    variants.append(_get_sld(host))
    seen = set()
    ordered = []
    for item in variants:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def load_opml_hosts(opml_dir: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    paths = sorted(glob.glob(os.path.join(opml_dir, "*.opml")))
    for path in paths:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            continue
        for outline in tree.findall(".//outline"):
            title = outline.get("text") or outline.get("title") or ""
            html_url = outline.get("htmlUrl") or ""
            xml_url = outline.get("xmlUrl") or ""
            variants = host_variants(html_url) or host_variants(xml_url)
            if not variants:
                continue
            if title:
                for host in variants:
                    if host not in mapping:
                        mapping[host] = title.strip()
    return mapping


def load_freshrss_hosts() -> Dict[str, str]:
    base_url = (os.getenv("FRESHRSS_BASE_URL") or "").rstrip("/")
    api_path = os.getenv("FRESHRSS_API_PATH", "/api/greader.php")
    username = os.getenv("FRESHRSS_USERNAME", "")
    password = os.getenv("FRESHRSS_API_PASSWORD", "")
    verify_ssl = (os.getenv("FRESHRSS_VERIFY_SSL", "true").lower() != "false")

    if not base_url or not username or not password:
        return {}

    api_root = f"{base_url}{api_path}"
    auth_url = f"{api_root}/accounts/ClientLogin"
    params = {"Email": username, "Passwd": password}
    with httpx.Client(verify=verify_ssl, timeout=20) as client:
        resp = client.get(auth_url, params=params)
        resp.raise_for_status()
        auth_token = None
        for line in resp.text.splitlines():
            if line.startswith("Auth="):
                auth_token = line.split("=", 1)[1].strip()
                break
        if not auth_token:
            return {}

        subs_url = f"{api_root}/reader/api/0/subscription/list"
        headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
        subs_resp = client.get(subs_url, headers=headers, params={"output": "json"})
        subs_resp.raise_for_status()
        data = subs_resp.json()

    mapping: Dict[str, str] = {}
    for sub in data.get("subscriptions", []):
        title = sub.get("title") or ""
        html_url = sub.get("htmlUrl") or ""
        xml_url = sub.get("xmlUrl") or ""
        variants = host_variants(html_url) or host_variants(xml_url)
        if title:
            for host in variants:
                if host and host not in mapping:
                    mapping[host] = title.strip()
    return mapping


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser("Backfill article sources from OPML feed names")
    p.add_argument("--db", required=True, help="SQLAlchemy DB URL")
    p.add_argument("--opml-dir", default="shared", help="Directory containing OPML files")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--where", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-freshrss-fallback", action="store_true")
    p.add_argument("--report-limit", type=int, default=50)
    p.add_argument("--overrides", default=None, help="JSON file with host->source overrides")
    args = p.parse_args()

    mapping = load_opml_hosts(args.opml_dir)
    if not mapping:
        print("No OPML feed mappings found.")
        mapping = {}

    if args.overrides:
        try:
            import json
            with open(args.overrides, "r", encoding="utf-8") as f:
                overrides = json.load(f)
            if isinstance(overrides, dict):
                for host, source in overrides.items():
                    if host and source:
                        mapping[host.strip().lower()] = str(source).strip()
        except Exception as exc:
            print(f"Failed to load overrides: {exc}")

    base_sql = """
      SELECT id, url, source
      FROM articles
      WHERE (source IS NULL OR source = '')
    """
    conditions = []
    if args.where:
        conditions.append(f"({args.where})")
    where_sql = (" AND " + " AND ".join(conditions)) if conditions else ""
    limit_sql = f" LIMIT {args.limit}" if args.limit and args.limit > 0 else ""
    select_sql = base_sql + where_sql + " ORDER BY id" + limit_sql

    update_sql = text("UPDATE articles SET source = :source WHERE id = :id")

    processed = 0
    matched = 0
    updated = 0
    pending = 0
    unmapped: Dict[str, int] = {}
    missing_hosts: Dict[str, int] = {}

    engine = create_engine(args.db, future=True)
    with Session(engine) as session:
        rows = session.execute(text(select_sql)).mappings()
        rows = list(rows)

        host_to_ids: Dict[str, list] = {}
        for row in rows:
            processed += 1
            variants = host_variants(row["url"] or "")
            if not variants:
                continue
            primary = normalize_host(row["url"] or "") or variants[0]
            host_to_ids.setdefault(primary, []).append(row["id"])
            source = None
            for host in variants:
                source = mapping.get(host)
                if source:
                    break
            if not source:
                missing_hosts[primary] = missing_hosts.get(primary, 0) + 1
                continue
            matched += 1
            if args.dry_run:
                continue
            session.execute(update_sql, {"id": row["id"], "source": source})
            updated += 1
            pending += 1
            if pending >= args.batch_size:
                session.commit()
                pending = 0

        if missing_hosts and not args.no_freshrss_fallback:
            freshrss_mapping = load_freshrss_hosts()
            for host, count in list(missing_hosts.items()):
                source = freshrss_mapping.get(host)
                if not source:
                    unmapped[host] = count
                    continue
                matched += count
                if args.dry_run:
                    continue
                for row_id in host_to_ids.get(host, []):
                    session.execute(update_sql, {"id": row_id, "source": source})
                    updated += 1
                    pending += 1
                    if pending >= args.batch_size:
                        session.commit()
                        pending = 0
        else:
            unmapped = missing_hosts

        if not args.dry_run and pending:
            session.commit()

    print("\n=== Backfill Sources Report ===")
    print(f"OPML directory: {args.opml_dir}")
    print(f"Processed: {processed}")
    print(f"Matched hosts: {matched}")
    print(f"Updated: {0 if args.dry_run else updated}")
    if unmapped:
        print("\nUnmapped hosts (top):")
        for host, count in sorted(unmapped.items(), key=lambda kv: kv[1], reverse=True)[: args.report_limit]:
            print(f"  {host}: {count}")
    if args.dry_run:
        print("Dry-run: no DB writes performed.")


if __name__ == "__main__":
    main()
