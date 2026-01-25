#!/usr/bin/env python3
"""
build_l1_anchors.py

Build BM25-safe anchor candidates for IPTC L1 topics using weak labels from OPML feed groupings.
No LLM usage. No embeddings. Pure lexical stats.

Inputs:
- IPTC taxonomy JSON (your L1/L2 export) to discover L1 nodes
- One or more OPML files: each represents a "source group" (technology, news, etc.)
- Articles from either:
  A) JSONL file (recommended for portability)
  B) Postgres DB via SQLAlchemy

Core idea:
- Use OPML membership to assign each article to a source group (by feed title).
- Map source groups to IPTC L1 buckets (auto mapping + optional overrides).
- Extract n-grams (1..N) from cleaned article text, compute document frequency (DF)
- Score phrases per L1 by log-odds (distinctiveness vs other L1 buckets)
- Output CSV + JSON patch (anchors per L1)

JSONL format expected (one JSON per line), minimal fields:
{
  "id": 123,
  "lang": "en",
  "source": "The Verge",          # should match OPML outline/@title/@text for best results
  "title": "...",
  "text": "cleaned plain text ...",  # preferably cleaned
  "url": "..."
}

DB mode expects a table with at least: id, lang, source, title, text
You can override column names.

Examples:

# JSONL mode (English)
python backend/tools/build_l1_anchors.py \
  --taxonomy shared/iptc_l1l2_full.json \
  --lang en \
  --articles-jsonl out/articles_en.jsonl \
  --opml-group technology="shared/technology - en.opml" \
  --opml-group science_environment="shared/science_environment.opml" \
  --opml-group news="shared/news - en.opml" \
  --opml-group culture_entertainment_sports="shared/culture_entertainment_sports.opml" \
  --opml-group long_essays="shared/long_essays.opml" \
  --max-ngram 4 \
  --min-df 6 \
  --max-anchors 150 \
  --out-csv out/anchors_candidates_l1_en.csv \
  --out-patch out/taxonomy_patch_l1_en.json

# DB mode (French)
python backend/tools/build_l1_anchors.py \
  --taxonomy shared/iptc_l1l2_full.json \
  --lang fr \
  --db postgresql://user:pass@localhost:5432/lumen_digest \
  --db-table articles \
  --db-text-col cleaned_text \
  --db-source-col source \
  --opml-group technology="shared/technology - en.opml" \
  ... \
  --out-csv out/anchors_candidates_l1_fr.csv \
  --out-patch out/taxonomy_patch_l1_fr.json

Then you review CSV and merge patch into taxonomy.
"""

import argparse
import csv
import json
import math
import re
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Iterable

# -------------------------
# Lightweight stopwords
# -------------------------
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
    "sera","seront","était","étaient","près","vers","chez"
}

# Reject overly generic tokens that often distort lexical matching
GENERIC_DENY_EN = {
    "world","people","issue","issues","action","actions","group","groups","system","systems","many","various",
    "such","including","general","public","national","international","report","reports","news","today",
    "week","month","year","said","says"
}
GENERIC_DENY_FR = {
    "monde","gens","personnes","question","questions","action","actions","groupe","groupes","système","systèmes",
    "plusieurs","divers","général","publique","national","internationale","rapport","rapports","actualités",
    "aujourd'hui","semaine","mois","an","a dit"
}

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]*")

def norm_lang(lang: str) -> str:
    return (lang or "").split("-")[0].lower().strip()

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def tokens(text: str) -> List[str]:
    return WORD_RE.findall(text.lower())

def is_acronym(tok: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{3,}", tok.strip()))

def boundary_stopword(phrase_toks: List[str], stop: set) -> bool:
    if not phrase_toks:
        return True
    return phrase_toks[0] in stop or phrase_toks[-1] in stop or all(t in stop for t in phrase_toks)

def contains_generic(phrase_toks: List[str], lang: str) -> bool:
    deny = GENERIC_DENY_EN if lang == "en" else GENERIC_DENY_FR
    return any(t in deny for t in phrase_toks)

def valid_phrase(phrase_toks: List[str], lang: str, min_chars: int) -> Tuple[bool, str]:
    stop = STOP_EN if lang == "en" else STOP_FR

    if not phrase_toks:
        return False, "empty"
    phrase = " ".join(phrase_toks)
    if len(phrase) < min_chars:
        return False, "too_short"
    if boundary_stopword(phrase_toks, stop):
        return False, "boundary_stopword"
    if contains_generic(phrase_toks, lang):
        return False, "contains_generic"

    # Single-word: allow acronyms or longer proper-ish tokens
    if len(phrase_toks) == 1:
        t = phrase_toks[0]
        if len(t) >= 5 and t.isalpha():
            return True, "ok_single"
        return False, "single_word"

    return True, "ok"

def ngrams_from_tokens(toks: List[str], max_ngram: int) -> Iterable[Tuple[str, ...]]:
    n = len(toks)
    for k in range(1, max_ngram + 1):
        if k > n:
            break
        for i in range(0, n - k + 1):
            yield tuple(toks[i:i+k])

# -------------------------
# OPML parsing (simple)
# -------------------------
def parse_opml_sources(path: str) -> List[Tuple[str, str]]:
    """
    Returns list of (feed_title, feed_xmlurl) tuples.
    OPML outlines usually contain attributes: text/title/xmlUrl/htmlUrl
    """
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()
    outlines = root.findall(".//outline")
    out = []
    for o in outlines:
        title = o.attrib.get("title") or o.attrib.get("text") or ""
        xmlurl = o.attrib.get("xmlUrl") or o.attrib.get("xmlurl") or ""
        title = normalize_space(title)
        xmlurl = normalize_space(xmlurl)
        if title or xmlurl:
            out.append((title, xmlurl))
    return out

# -------------------------
# Taxonomy L1 discovery
# -------------------------
def load_taxonomy_l1(path: str) -> Dict[str, Dict[str, str]]:
    """
    Returns l1_id -> {en_label, fr_label}
    Expects L1 nodes in tax["categories"].
    """
    with open(path, "r", encoding="utf-8") as f:
        tax = json.load(f)
    l1 = {}
    for cat in tax.get("categories", []) or []:
        cid = cat.get("id")
        labels = cat.get("labels", {}) or {}
        if cid:
            l1[cid] = {
                "en": labels.get("en") or cid,
                "fr": labels.get("fr") or labels.get("en") or cid,
            }
    return l1

def auto_map_groups_to_l1(group_names: List[str], l1_labels: Dict[str, Dict[str, str]]) -> Dict[str, List[str]]:
    """
    Heuristic mapping from OPML group name to one or more L1 IDs based on label keywords.
    You can override with --group-map-json.
    """
    # Build keyword->l1_id mapping from L1 English labels
    label_index = []
    for l1_id, labs in l1_labels.items():
        label_index.append((l1_id, (labs.get("en","") + " " + labs.get("fr","")).lower()))

    def find_l1_ids_by_keywords(keywords: List[str]) -> List[str]:
        hits = []
        for l1_id, blob in label_index:
            if any(k in blob for k in keywords):
                hits.append(l1_id)
        return hits

    mapping: Dict[str, List[str]] = {}

    for g in group_names:
        gl = g.lower()

        # Common OPML buckets
        if "tech" in gl or "technology" in gl:
            ids = find_l1_ids_by_keywords(["science and technology", "science", "technology"])
        elif "science" in gl or "environment" in gl:
            ids = find_l1_ids_by_keywords(["environment", "science and technology", "science"])
        elif "culture" in gl or "entertainment" in gl or "sports" in gl:
            ids = find_l1_ids_by_keywords(["arts, culture", "arts", "culture", "sport"])
        elif "news" in gl:
            # News is broad: politics, economy, conflict, society often dominate; keep it broad but not everything
            ids = find_l1_ids_by_keywords(["politics and government", "economy", "conflict", "society"])
        elif "essay" in gl:
            ids = find_l1_ids_by_keywords(["society", "human interest", "lifestyle"])
        else:
            ids = []

        # Fallback: if nothing matched, do not map automatically
        mapping[g] = ids

    return mapping

# -------------------------
# Article iterators
# -------------------------
def iter_articles_jsonl(path: str, lang: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if norm_lang(obj.get("lang","")) != lang:
                continue
            yield obj

def iter_articles_db(db_url: str, table: str, lang: str,
                     id_col: str, lang_col: str, title_col: str, text_col: str, source_col: str,
                     where: Optional[str] = None,
                     limit: Optional[int] = None) -> Iterable[dict]:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    w = f"WHERE {lang_col} = :lang" if lang_col else "WHERE 1=1"
    if where:
        w += f" AND ({where})"
    lim = f" LIMIT {int(limit)}" if limit else ""
    sql = f"""
      SELECT
        {id_col} AS id,
        {lang_col} AS lang,
        {title_col} AS title,
        {text_col} AS text,
        {source_col} AS source
      FROM {table}
      {w}
      {lim}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"lang": lang}).mappings()
        for r in rows:
            yield dict(r)

# -------------------------
# Core scoring
# -------------------------
@dataclass
class PhraseStats:
    df_in: int
    df_out: int
    score: float
    examples: List[str]

def log_odds(df_in: int, n_in: int, df_out: int, n_out: int) -> float:
    # add-one smoothing
    p_in = (df_in + 1.0) / (n_in + 2.0)
    p_out = (df_out + 1.0) / (n_out + 2.0)
    return math.log(p_in / p_out)

def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--lang", choices=["en","fr"], required=True)

    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--articles-jsonl", help="JSONL with cleaned text, source, lang")
    src.add_argument("--db", help="SQLAlchemy DB URL (postgresql://...)")

    ap.add_argument("--db-table", default="articles")
    ap.add_argument("--db-id-col", default="id")
    ap.add_argument("--db-lang-col", default="lang")
    ap.add_argument("--db-title-col", default="title")
    ap.add_argument("--db-text-col", default="text")
    ap.add_argument("--db-source-col", default="source")
    ap.add_argument("--db-where", default=None, help="Optional SQL WHERE fragment (without 'WHERE')")
    ap.add_argument("--db-limit", type=int, default=None)

    ap.add_argument("--opml-group", action="append", default=[],
                    help='GroupName="path/to/file.opml" (repeatable)')
    ap.add_argument("--group-map-json", default=None,
                    help="Optional JSON mapping {group_name: [l1_id,...]} to override auto mapping")

    ap.add_argument("--max-ngram", type=int, default=4)
    ap.add_argument("--min-df", type=int, default=5)
    ap.add_argument("--min-chars", type=int, default=4)
    ap.add_argument("--max-anchors", type=int, default=150)
    ap.add_argument("--max-candidates-per-l1", type=int, default=2000)
    ap.add_argument("--min-docs-per-l1", type=int, default=25, help="Skip L1 buckets with too few docs")

    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--out-patch", required=True)

    args = ap.parse_args()

    if not args.opml_group:
        raise SystemExit("Provide at least one --opml-group GroupName=path.opml")

    l1_labels = load_taxonomy_l1(args.taxonomy)

    # Parse OPML groups
    group_to_feed_titles = defaultdict(set)
    group_names = []
    for spec in args.opml_group:
        if "=" not in spec:
            raise SystemExit(f"Invalid --opml-group: {spec} (expected GroupName=path)")
        gname, path = spec.split("=", 1)
        gname = gname.strip().strip('"').strip("'")
        path = path.strip().strip('"').strip("'")
        group_names.append(gname)
        for title, _xmlurl in parse_opml_sources(path):
            if title:
                group_to_feed_titles[gname].add(title.lower())

    # Map groups -> L1 IDs
    if args.group_map_json:
        with open(args.group_map_json, "r", encoding="utf-8") as f:
            group_to_l1 = json.load(f)
    else:
        group_to_l1 = auto_map_groups_to_l1(group_names, l1_labels)

    # Build feed-title -> groups reverse index
    feed_title_to_groups = defaultdict(list)
    for g, titles in group_to_feed_titles.items():
        for t in titles:
            feed_title_to_groups[t].append(g)

    # Ingest articles
    if args.articles_jsonl:
        article_iter = iter_articles_jsonl(args.articles_jsonl, args.lang)
    else:
        article_iter = iter_articles_db(
            db_url=args.db,
            table=args.db_table,
            lang=args.lang,
            id_col=args.db_id_col,
            lang_col=args.db_lang_col,
            title_col=args.db_title_col,
            text_col=args.db_text_col,
            source_col=args.db_source_col,
            where=args.db_where,
            limit=args.db_limit
        )

    # Bucket docs by L1 using source-group mapping
    l1_docs: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # l1_id -> [(doc_id, text)]
    unmapped = 0
    total = 0

    for a in article_iter:
        total += 1
        doc_id = str(a.get("id", total))
        source = normalize_space(a.get("source","")).lower()
        text = normalize_space(a.get("text",""))
        title = normalize_space(a.get("title",""))

        if not text or len(text) < 200:
            continue

        # Find groups by source title exact match; if not found, try fuzzy-ish fallback
        groups = feed_title_to_groups.get(source, [])
        if not groups:
            # fallback: best-effort contains match against known feed titles
            for ft in feed_title_to_groups.keys():
                if ft and ft in source:
                    groups = feed_title_to_groups[ft]
                    break

        if not groups:
            unmapped += 1
            continue

        # Map groups -> L1 IDs
        l1_ids = set()
        for g in groups:
            for l1_id in group_to_l1.get(g, []) or []:
                l1_ids.add(l1_id)

        if not l1_ids:
            # no mapping configured; skip
            continue

        # Use title+text for candidate extraction; title gets a small duplication bump
        combined = f"{title}\n{text}\n{title}"
        for l1_id in l1_ids:
            l1_docs[l1_id].append((doc_id, combined))

    if not l1_docs:
        raise SystemExit(
            "No articles mapped to any L1. "
            "Likely cause: article.source doesn't match OPML feed titles. "
            "Fix by exporting feed URL/title into your DB/JSONL or provide a group-map JSON and better source matching."
        )

    # Build per-L1 DF
    stop = STOP_EN if args.lang == "en" else STOP_FR

    # Total docs per L1 and global
    l1_doc_counts = {l1: len(docs) for l1, docs in l1_docs.items()}
    global_docs = sum(l1_doc_counts.values())

    # DF per L1: phrase -> df
    l1_df: Dict[str, Counter] = {l1: Counter() for l1 in l1_docs.keys()}
    # Global DF: phrase -> df
    global_df = Counter()
    # Keep examples
    l1_examples: Dict[str, Dict[Tuple[str, ...], List[str]]] = defaultdict(lambda: defaultdict(list))

    for l1_id, docs in l1_docs.items():
        if len(docs) < args.min_docs_per_l1:
            continue
        for doc_id, text in docs:
            toks = tokens(text)
            # doc-level unique ngrams for DF counting
            seen = set()
            for ng in ngrams_from_tokens(toks, args.max_ngram):
                ok, _reason = valid_phrase(list(ng), args.lang, args.min_chars)
                if not ok:
                    continue
                # quick reject: remove phrases containing stopwords internally only if very short
                if len(ng) <= 2 and any(t in stop for t in ng):
                    continue
                if ng in seen:
                    continue
                seen.add(ng)
            for ng in seen:
                l1_df[l1_id][ng] += 1
                global_df[ng] += 1
                ex = l1_examples[l1_id][ng]
                if len(ex) < 3:
                    ex.append(doc_id)

    # Score per L1
    rows = []
    patch = {"version": "l1_anchor_patch_v1", "lang": args.lang, "anchors": {}}

    for l1_id, df_counter in l1_df.items():
        n_in = l1_doc_counts.get(l1_id, 0)
        if n_in < args.min_docs_per_l1:
            continue
        n_out = max(1, global_docs - n_in)

        candidates = []
        for phrase_ng, df_in in df_counter.items():
            if df_in < args.min_df:
                continue
            df_all = global_df[phrase_ng]
            df_out = max(0, df_all - df_in)

            # Distinctiveness
            s = log_odds(df_in, n_in, df_out, n_out)

            # Mild preference for multi-word phrases (BM25 stability)
            s += 0.08 * (len(phrase_ng) - 1)

            candidates.append((s, phrase_ng, df_in, df_out))

        candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = candidates[:args.max_candidates_per_l1]

        # Build anchors list
        anchors = []
        for s, phrase_ng, df_in, df_out in candidates[:args.max_anchors]:
            phrase = " ".join(phrase_ng)
            anchors.append(phrase)
            rows.append({
                "l1_id": l1_id,
                "l1_label": l1_labels.get(l1_id, {}).get(args.lang) or l1_labels.get(l1_id, {}).get("en") or l1_id,
                "lang": args.lang,
                "phrase": phrase,
                "df_in": df_in,
                "df_out": df_out,
                "score": round(s, 6),
                "examples": ",".join(l1_examples[l1_id].get(phrase_ng, [])),
            })

        patch["anchors"][l1_id] = anchors

    # Write CSV
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["l1_id","l1_label","lang","phrase","df_in","df_out","score","examples"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Write patch JSON
    with open(args.out_patch, "w", encoding="utf-8") as f:
        json.dump(patch, f, ensure_ascii=False, indent=2)

    print("=== L1 Anchor Build Report ===")
    print(f"Lang: {args.lang}")
    print(f"Articles seen: {total}")
    print(f"Unmapped (no OPML source match): {unmapped}")
    print(f"L1 buckets built: {len(patch['anchors'])}")
    print(f"Wrote CSV:   {args.out_csv}")
    print(f"Wrote patch: {args.out_patch}")
    print("\nNOTE: Review the CSV, then merge anchors into taxonomy (L1 only).")


if __name__ == "__main__":
    main()