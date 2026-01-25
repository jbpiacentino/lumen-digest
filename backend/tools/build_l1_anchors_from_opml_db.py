#!/usr/bin/env python3
"""
Build L1 anchor candidates (BM25-safe) using weak labels from a single OPML file (folder/grouped feeds)
and articles stored in Postgres.

Assumes your articles table contains:
- id
- lang ('en' or 'fr')
- title
- cleaned_text (or text)
- feed_title and/or feed_url (preferred)
  If you only have 'source' as a publisher name, matching to OPML will be weak.

Outputs:
- CSV: anchor candidates per L1
- JSON patch: anchors per L1 (ready to merge into taxonomy)
"""

import argparse
import csv
import json
import math
import re
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple, Iterable

from sqlalchemy import create_engine, text as sql_text

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]*")

STOP_EN = {
    "a","an","and","are","as","at","be","but","by","for","from","has","have","he","her","his","i",
    "in","into","is","it","its","of","on","or","that","the","their","they","this","to","was","were",
    "will","with","you","your","we","our","not","than","then","so","if","about","after","before",
    "over","under","between","because","also","more","most","can","could","should","would"
}
STOP_FR = {
    "un","une","des","et","ou","à","au","aux","de","du","des","dans","en","sur","pour","par","avec",
    "sans","ce","ces","cet","cette","qui","que","quoi","dont","où","il","elle","ils","elles","on","nous",
    "vous","je","tu","me","te","se","lui","leur","les","la","le","d","l","c","n","ne","pas","plus",
    "moins","comme","mais","donc","or","ni","car","ainsi","été","être","avait","ont","a","est","sont",
    "sera","seront","était","étaient"
}

GENERIC_DENY_EN = {"world","people","issue","issues","action","actions","group","groups","system","systems",
                   "general","public","national","international","report","reports","news","today","said","says"}
GENERIC_DENY_FR = {"monde","gens","personnes","question","questions","action","actions","groupe","groupes",
                   "système","systèmes","général","publique","national","internationale","rapport","rapports",
                   "actualités","aujourd'hui"}

def norm_lang(lang: str) -> str:
    return (lang or "").split("-")[0].lower().strip()

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def tokens(text: str) -> List[str]:
    return WORD_RE.findall(text.lower())

def boundary_stopword(phrase_toks: List[str], stop: set) -> bool:
    return (not phrase_toks) or phrase_toks[0] in stop or phrase_toks[-1] in stop or all(t in stop for t in phrase_toks)

def contains_generic(phrase_toks: List[str], lang: str) -> bool:
    deny = GENERIC_DENY_EN if lang == "en" else GENERIC_DENY_FR
    return any(t in deny for t in phrase_toks)

def valid_phrase(phrase_toks: List[str], lang: str, min_chars: int) -> bool:
    stop = STOP_EN if lang == "en" else STOP_FR
    phrase = " ".join(phrase_toks)
    if len(phrase) < min_chars:
        return False
    if boundary_stopword(phrase_toks, stop):
        return False
    if contains_generic(phrase_toks, lang):
        return False
    # single-word anchors are usually too noisy; keep only long alpha tokens
    if len(phrase_toks) == 1:
        t = phrase_toks[0]
        return t.isalpha() and len(t) >= 6
    return True

def ngrams_from_tokens(toks: List[str], max_ngram: int) -> Iterable[Tuple[str, ...]]:
    n = len(toks)
    for k in range(1, max_ngram + 1):
        if k > n:
            break
        for i in range(0, n - k + 1):
            yield tuple(toks[i:i+k])

def load_taxonomy_l1(path: str) -> Dict[str, Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    l1 = {}
    for cat in tax.get("categories", []) or []:
        cid = cat.get("id")
        labels = cat.get("labels", {}) or {}
        if cid:
            l1[cid] = {"en": labels.get("en") or cid, "fr": labels.get("fr") or labels.get("en") or cid}
    return l1

def auto_map_groups_to_l1(group_names: List[str], l1_labels: Dict[str, Dict[str, str]]) -> Dict[str, List[str]]:
    # very conservative heuristic; override with --group-map-json for accuracy
    idx = [(l1_id, (labs["en"] + " " + labs["fr"]).lower()) for l1_id, labs in l1_labels.items()]

    def match(keys: List[str]) -> List[str]:
        out = []
        for l1_id, blob in idx:
            if any(k in blob for k in keys):
                out.append(l1_id)
        return out

    out = {}
    for g in group_names:
        gl = g.lower()
        if any(k in gl for k in ["tech", "technology", "software", "it"]):
            out[g] = match(["science and technology"])
        elif any(k in gl for k in ["science", "environment", "climate"]):
            out[g] = match(["environment", "science and technology"])
        elif any(k in gl for k in ["business", "finance", "economy", "markets", "vc"]):
            out[g] = match(["economy, business and finance"])
        elif any(k in gl for k in ["politics", "government", "geopolitics", "law"]):
            out[g] = match(["politics and government", "crime, law and justice"])
        elif any(k in gl for k in ["culture", "entertainment", "media", "arts"]):
            out[g] = match(["arts, culture, entertainment and media"])
        elif any(k in gl for k in ["sport", "sports"]):
            out[g] = match(["sport"])
        else:
            out[g] = []
    return out

def parse_opml_grouped(path: str) -> Dict[str, Dict[str, set]]:
    """
    Parses an OPML where top-level outline nodes represent groups (folders),
    and nested outline nodes represent feeds (with title/text + xmlUrl).

    Returns:
      group -> {"titles": set(lower_titles), "xmlurls": set(lower_xmlurls)}
    """
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()

    groups: Dict[str, Dict[str, set]] = defaultdict(lambda: {"titles": set(), "xmlurls": set()})

    # Common structure: body/outline (group)/outline (feed)
    body = root.find("body")
    if body is None:
        return groups

    for group_node in body.findall("./outline"):
        gname = normalize_space(group_node.attrib.get("title") or group_node.attrib.get("text") or "ungrouped")
        gname = gname or "ungrouped"

        # Feeds can be direct children or deeper
        for feed in group_node.findall(".//outline"):
            title = normalize_space(feed.attrib.get("title") or feed.attrib.get("text") or "")
            xmlurl = normalize_space(feed.attrib.get("xmlUrl") or feed.attrib.get("xmlurl") or "")
            if title:
                groups[gname]["titles"].add(title.lower())
            if xmlurl:
                groups[gname]["xmlurls"].add(xmlurl.lower())

    return groups

def log_odds(df_in: int, n_in: int, df_out: int, n_out: int) -> float:
    p_in = (df_in + 1.0) / (n_in + 2.0)
    p_out = (df_out + 1.0) / (n_out + 2.0)
    return math.log(p_in / p_out)

def iter_articles_db(engine, table: str, lang: str,
                     id_col: str, lang_col: str,
                     title_col: str, text_col: str,
                     feed_title_col: Optional[str],
                     feed_url_col: Optional[str],
                     where: Optional[str], limit: Optional[int]) -> Iterable[dict]:
    where_sql = f"WHERE {lang_col} = :lang" if lang_col else "WHERE 1=1"
    if where:
        where_sql += f" AND ({where})"
    lim = f" LIMIT {int(limit)}" if limit else ""

    cols = [
        f"{id_col} AS id",
        f"{lang_col} AS lang",
        f"{title_col} AS title",
        f"{text_col} AS text",
    ]
    if feed_title_col:
        cols.append(f"{feed_title_col} AS feed_title")
    else:
        cols.append("NULL::text AS feed_title")
    if feed_url_col:
        cols.append(f"{feed_url_col} AS feed_url")
    else:
        cols.append("NULL::text AS feed_url")

    sql = f"SELECT {', '.join(cols)} FROM {table} {where_sql} {lim}"
    with engine.connect() as conn:
        rows = conn.execute(sql_text(sql), {"lang": lang}).mappings()
        for r in rows:
            yield dict(r)

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--lang", choices=["en","fr"], required=True)

    ap.add_argument("--db", required=True)
    ap.add_argument("--db-table", default="articles")
    ap.add_argument("--db-id-col", default="id")
    ap.add_argument("--db-lang-col", default="lang")
    ap.add_argument("--db-title-col", default="title")
    ap.add_argument("--db-text-col", default="cleaned_text")
    ap.add_argument("--db-feed-title-col", default="feed_title")
    ap.add_argument("--db-feed-url-col", default="feed_url")
    ap.add_argument("--db-where", default=None)
    ap.add_argument("--db-limit", type=int, default=None)

    ap.add_argument("--opml", required=True, help="Single OPML with grouped feeds")
    ap.add_argument("--group-map-json", default=None, help="Optional override mapping {group_name:[l1_id,...]}")

    ap.add_argument("--max-ngram", type=int, default=4)
    ap.add_argument("--min-df", type=int, default=5)
    ap.add_argument("--min-chars", type=int, default=4)
    ap.add_argument("--min-docs-per-l1", type=int, default=20)
    ap.add_argument("--max-anchors", type=int, default=150)
    ap.add_argument("--max-candidates-per-l1", type=int, default=2000)

    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-patch", required=True)

    args = ap.parse_args()

    l1_labels = load_taxonomy_l1(args.taxonomy)

    groups = parse_opml_grouped(args.opml)
    group_names = list(groups.keys())

    if args.group_map_json:
        with open(args.group_map_json, "r", encoding="utf-8") as f:
            group_to_l1 = json.load(f)
    else:
        group_to_l1 = auto_map_groups_to_l1(group_names, l1_labels)

    # Reverse index for matching
    title_to_groups = defaultdict(list)
    url_to_groups = defaultdict(list)
    for g, d in groups.items():
        for t in d["titles"]:
            title_to_groups[t].append(g)
        for u in d["xmlurls"]:
            url_to_groups[u].append(g)

    engine = create_engine(args.db)

    # Bucket docs by L1 (weak supervision via OPML group mapping)
    l1_docs = defaultdict(list)  # l1_id -> [(doc_id, combined_text)]
    total = 0
    matched = 0

    for a in iter_articles_db(
        engine, args.db_table, args.lang,
        args.db_id_col, args.db_lang_col,
        args.db_title_col, args.db_text_col,
        args.db_feed_title_col if args.db_feed_title_col else None,
        args.db_feed_url_col if args.db_feed_url_col else None,
        args.db_where, args.db_limit
    ):
        total += 1
        doc_id = str(a.get("id", total))
        title = normalize_space(a.get("title",""))
        text = normalize_space(a.get("text",""))
        feed_title = normalize_space(a.get("feed_title","")).lower()
        feed_url = normalize_space(a.get("feed_url","")).lower()

        if not text or len(text) < 200:
            continue

        groups_hit = []
        if feed_url and feed_url in url_to_groups:
            groups_hit = url_to_groups[feed_url]
        elif feed_title and feed_title in title_to_groups:
            groups_hit = title_to_groups[feed_title]

        if not groups_hit:
            continue

        matched += 1

        l1_ids = set()
        for g in groups_hit:
            for l1_id in (group_to_l1.get(g) or []):
                l1_ids.add(l1_id)

        if not l1_ids:
            continue

        combined = f"{title}\n{text}\n{title}"
        for l1_id in l1_ids:
            l1_docs[l1_id].append((doc_id, combined))

    if not l1_docs:
        raise SystemExit(
            "No articles mapped to any L1. "
            "Check that your DB has feed_title/feed_url columns matching OPML outline titles/xmlUrl."
        )

    # Build DF counts
    stop = STOP_EN if args.lang == "en" else STOP_FR
    l1_doc_counts = {l1: len(docs) for l1, docs in l1_docs.items()}
    global_docs = sum(l1_doc_counts.values())

    l1_df = {l1: Counter() for l1 in l1_docs.keys()}
    global_df = Counter()
    examples = defaultdict(lambda: defaultdict(list))

    for l1_id, docs in l1_docs.items():
        if len(docs) < args.min_docs_per_l1:
            continue
        for doc_id, txt in docs:
            toks = tokens(txt)
            seen = set()
            for ng in ngrams_from_tokens(toks, args.max_ngram):
                if not valid_phrase(list(ng), args.lang, args.min_chars):
                    continue
                if len(ng) <= 2 and any(t in stop for t in ng):
                    continue
                seen.add(ng)
            for ng in seen:
                l1_df[l1_id][ng] += 1
                global_df[ng] += 1
                ex = examples[l1_id][ng]
                if len(ex) < 3:
                    ex.append(doc_id)

    # Score + output
    rows = []
    patch = {"version": "l1_anchor_patch_v1", "lang": args.lang, "anchors": {}}

    for l1_id, df_counter in l1_df.items():
        n_in = l1_doc_counts.get(l1_id, 0)
        if n_in < args.min_docs_per_l1:
            continue
        n_out = max(1, global_docs - n_in)

        cand = []
        for ng, df_in in df_counter.items():
            if df_in < args.min_df:
                continue
            df_out = max(0, global_df[ng] - df_in)
            s = log_odds(df_in, n_in, df_out, n_out)
            s += 0.08 * (len(ng) - 1)  # small bonus for multi-word anchors
            cand.append((s, ng, df_in, df_out))

        cand.sort(key=lambda x: x[0], reverse=True)
        cand = cand[:args.max_candidates_per_l1]

        anchors = []
        for s, ng, df_in, df_out in cand[:args.max_anchors]:
            phrase = " ".join(ng)
            anchors.append(phrase)
            rows.append({
                "l1_id": l1_id,
                "l1_label": l1_labels.get(l1_id, {}).get(args.lang) or l1_labels.get(l1_id, {}).get("en") or l1_id,
                "lang": args.lang,
                "phrase": phrase,
                "df_in": df_in,
                "df_out": df_out,
                "score": round(s, 6),
                "examples": ",".join(examples[l1_id][ng]),
            })

        patch["anchors"][l1_id] = anchors

    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["l1_id","l1_label","lang","phrase","df_in","df_out","score","examples"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    with open(args.out_patch, "w", encoding="utf-8") as f:
        json.dump(patch, f, ensure_ascii=False, indent=2)

    print("=== L1 Anchor Build (DB+OPML) Report ===")
    print(f"Lang: {args.lang}")
    print(f"Rows scanned: {total}")
    print(f"Articles matched to OPML groups: {matched}")
    print(f"L1 buckets produced: {len(patch['anchors'])}")
    print(f"Wrote CSV:   {args.out_csv}")
    print(f"Wrote patch: {args.out_patch}")
    print("Next: review CSV and merge patch into taxonomy.")
    print("Tip: if matched is low, ensure feed_title/feed_url in DB match OPML outline title/xmlUrl.")

if __name__ == "__main__":
    main()