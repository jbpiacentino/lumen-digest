#!/usr/bin/env python3
"""
Build L1 anchor candidates (BM25-safe) from Postgres using a "source group" column
like: "NYT ＞ World" (or "NYT > World").

No OPML required.

- Parses group from source via separators (＞, >, /, |)
- Optional fallback: derive group from article URL path (/world/, /business/, etc.)
- Uses group->L1 mapping (JSON) to bucket docs
- Extracts n-grams, scores by log-odds distinctiveness per L1
- Outputs CSV + JSON patch for taxonomy anchors

Example:
python backend/tools/build_l1_anchors_from_db_groups.py \
  --taxonomy shared/iptc_l1l2_en_fr.json \
  --lang en \
  --db postgresql://lumen_admin:password@localhost:5432/lumen_digest \
  --db-table articles \
  --db-id-col id \
  --db-lang-col language \
  --db-title-col title \
  --db-text-col full_text \
  --db-source-col source \
  --db-url-col url \
  --group-map-json shared/nyt_group_map_l1.json \
  --max-ngram 4 --min-df 5 --max-anchors 150 \
  --out-csv anchors_candidates_l1_en.csv \
  --out-patch taxonomy_patch_l1_en.json
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

DENY_TOKENS = {
    # URL / markup residue
    "https","http","www","com","html","htm","php","asp",
    # Publisher / navigation / UI boilerplate
    "nytimes","wsj","ft","bloomberg","reuters","apnews","cnn","bbc",
    "advertisement","subscribe","subscription","newsletter","sign","signup","sign-up","gift",
    "read","more","cookie","cookies","privacy","terms","share","link",
    "facebook","twitter","instagram","tiktok","youtube",
    "after-bottom","afterbottom","before-bottom","beforebottom",
    "verified"
}

URL_RE = re.compile(r"https?://\S+|www\.\S+")
HTML_TAG_RE = re.compile(r"<[^>]+>")
NON_TEXT_RE = re.compile(r"(?:\b(?:advertisement|subscribe|newsletter|sign up|sign-up|read more)\b)", re.I)

DOTTED_ACRONYM_RE = re.compile(
    r"\b([A-Za-z])\.\s*([A-Za-z])\.(?:\s*([A-Za-z])\.)?(?:\s*([A-Za-z])\.)?\b"
)

DENY_PHRASE_RE = re.compile(
    r"(after-bottom|before-bottom|continue reading|sign up|newsletter|advertisement|subscribe|subscription)",
    re.I
)

# These are strong "crime blotter" templates that pollute anchors when a bucket is mixed.
# Apply only for English anchor generation (see valid_phrase).
# VIOLENCE_TEMPLATE_RE = re.compile(
#     r"\b(shot and killed|who was killed|who was shot|fatally shot|fatal shooting|criminal record)\b",
#     re.I
# )

ACRONYM_SPACED_MAP = {
    # Merge spaced acronyms that often appear after aggressive punctuation stripping.
    # Keep this allowlist small and auditable.
    r"\bU\s+S\b": "US",
    r"\bU\s+K\b": "UK",
    r"\bU\s+N\b": "UN",
    r"\bE\s+U\b": "EU",
    r"\bN\s+A\s+T\s+O\b": "NATO",
}

def normalize_spaced_acronyms(s: str) -> str:
    # Case-insensitive matching; replacement is uppercase. Tokenization lowercases later.
    for pat, rep in ACRONYM_SPACED_MAP.items():
        s = re.sub(pat, rep, s, flags=re.I)
    return s

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

def numeric_heavy(phrase_toks: List[str]) -> bool:
    digits = sum(any(ch.isdigit() for ch in t) for t in phrase_toks)
    return digits >= max(1, len(phrase_toks) // 2)

def valid_phrase(phrase_toks: List[str], lang: str, min_chars: int) -> bool:
    stop = STOP_EN if lang == "en" else STOP_FR
    phrase = " ".join(phrase_toks)

    if len(phrase) < min_chars:
        return False
    if boundary_stopword(phrase_toks, stop):
        return False
    if contains_generic(phrase_toks, lang):
        return False
    if numeric_heavy(phrase_toks):
        return False

    # Boilerplate / UI fragments
    if DENY_PHRASE_RE.search(phrase):
        return False
    if any(t in DENY_TOKENS for t in phrase_toks):
        return False

    # Avoid single-letter artifacts in English (e.g. "former u s", "s politics democratic").
    # Do NOT apply this to French, where single-letter tokens can be legitimate.
    if lang == "en" and any(len(t) == 1 for t in phrase_toks):
        return False

    # Drop common violence templates that do not help L1 "politics and government" anchoring.
    # if lang == "en" and VIOLENCE_TEMPLATE_RE.search(phrase):
    #     return False

    # 1-gram: keep only substantive alpha tokens
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

# --- group extraction ---

GROUP_SEP_RE = re.compile(r"\s*(?:＞|>|/|\||:)\s*")

def group_from_source(source: str) -> Optional[str]:
    """
    "NYT ＞ World" -> "World"
    If multiple parts, take last.
    """
    s = normalize_space(source)
    if not s:
        return None
    parts = [p.strip() for p in GROUP_SEP_RE.split(s) if p.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return parts[0] if parts else None

def group_from_url(url: str) -> Optional[str]:
    """
    NYT URL path heuristic:
    https://www.nytimes.com/2026/01/24/world/canada/... -> "world"
    """
    u = (url or "").strip()
    m = re.match(r"^https?://(www\.)?nytimes\.com/\d{4}/\d{2}/\d{2}/([^/]+)/", u)
    if m:
        return m.group(2)
    return None

def log_odds(df_in: int, n_in: int, df_out: int, n_out: int) -> float:
    p_in = (df_in + 1.0) / (n_in + 2.0)
    p_out = (df_out + 1.0) / (n_out + 2.0)
    return math.log(p_in / p_out)

def iter_articles_db(engine, table: str, lang: str,
                     id_col: str, lang_col: str, title_col: str, text_col: str,
                     source_col: str, url_col: str,
                     where: Optional[str], limit: Optional[int]) -> Iterable[dict]:
    where_sql = f"WHERE {lang_col} = :lang" if lang_col else "WHERE 1=1"
    if where:
        where_sql += f" AND ({where})"
    lim = f" LIMIT {int(limit)}" if limit else ""
    sql = f"""
      SELECT
        {id_col} AS id,
        {lang_col} AS lang,
        {title_col} AS title,
        {text_col} AS text,
        {source_col} AS source,
        {url_col} AS url
      FROM {table}
      {where_sql}
      {lim}
    """
    with engine.connect() as conn:
        rows = conn.execute(sql_text(sql), {"lang": lang}).mappings()
        for r in rows:
            yield dict(r)


def normalize_dotted_acronyms(s: str) -> str:
    # U.S. -> US ; U.K. -> UK ; U.N. -> UN ; E.U. -> EU ; I.B.M. -> IBM
    def repl(m: re.Match) -> str:
        return "".join([g for g in m.groups() if g])
    return DOTTED_ACRONYM_RE.sub(repl, s)

def preclean_text(s: str) -> str:
    s = s or ""
    s = HTML_TAG_RE.sub(" ", s)
    s = URL_RE.sub(" ", s)
    s = s.replace("\u00a0", " ")  # nbsp

    # Normalize common acronym formatting before tokenization.
    # - Dotted: "U.S." -> "US"
    # - Spaced: "U S"  -> "US" (can happen after aggressive punctuation stripping)
    s = normalize_dotted_acronyms(s)
    s = normalize_spaced_acronyms(s)

    # Strip possessive marker in English-like constructs ("Trump's" -> "Trump")
    s = re.sub(r"\b([A-Za-zÀ-ÖØ-öø-ÿ]+)['’]s\b", r"\1", s)

    s = NON_TEXT_RE.sub(" ", s)
    s = re.sub(r"\b(?:com|www|http|https|html|htm|php|asp)\b", " ", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--lang", choices=["en","fr"], required=True)

    ap.add_argument("--db", required=True)
    ap.add_argument("--db-table", default="articles")
    ap.add_argument("--db-id-col", default="id")
    ap.add_argument("--db-lang-col", default="lang")
    ap.add_argument("--db-title-col", default="title")
    ap.add_argument("--db-text-col", default="full_text")
    ap.add_argument("--db-source-col", default="source")
    ap.add_argument("--db-url-col", default="url")
    ap.add_argument("--db-where", default=None)
    ap.add_argument("--db-limit", type=int, default=None)

    ap.add_argument("--group-map-json", required=True, help="Mapping {group_name: [l1_id,...]}")

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
    with open(args.group_map_json, "r", encoding="utf-8") as f:
        group_to_l1 = json.load(f)

    engine = create_engine(args.db)

    l1_docs = defaultdict(list)  # l1_id -> [(doc_id, text)]
    total = 0
    grouped = 0

    for a in iter_articles_db(
        engine, args.db_table, args.lang,
        args.db_id_col, args.db_lang_col, args.db_title_col, args.db_text_col,
        args.db_source_col, args.db_url_col,
        args.db_where, args.db_limit
    ):
        total += 1
        doc_id = str(a.get("id", total))
        title = normalize_space(a.get("title",""))
        text = normalize_space(a.get("text",""))
        if not text or len(text) < 200:
            continue

        grp = group_from_source(a.get("source",""))
        if not grp:
            grp = group_from_url(a.get("url",""))

        if not grp:
            continue

        grouped += 1

        # normalize group key for map lookup (case-insensitive)
        grp_key = grp.strip()
        l1_ids = group_to_l1.get(grp_key) or group_to_l1.get(grp_key.lower()) or []

        if not l1_ids:
            continue

        combined = preclean_text(f"{title}\n{text}\n{title}")
        for l1_id in l1_ids:
            l1_docs[l1_id].append((doc_id, combined))

    if not l1_docs:
        raise SystemExit(
            "No articles mapped to any L1. "
            "Fix group_map_json keys to match extracted groups from source/url."
        )

    l1_doc_counts = {l1: len(docs) for l1, docs in l1_docs.items()}
    global_docs = sum(l1_doc_counts.values())

    stop = STOP_EN if args.lang == "en" else STOP_FR
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
            s += 0.08 * (len(ng) - 1)  # prefer multi-word
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

    print("=== L1 Anchor Build (DB groups) Report ===")
    print(f"Lang: {args.lang}")
    print(f"Rows scanned: {total}")
    print(f"Rows with extracted group: {grouped}")
    print(f"L1 buckets produced: {len(patch['anchors'])}")
    print(f"Wrote CSV:   {args.out_csv}")
    print(f"Wrote patch: {args.out_patch}")

if __name__ == "__main__":
    main()