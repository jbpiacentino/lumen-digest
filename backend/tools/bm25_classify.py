#!/usr/bin/env python3
"""
bm25_classify.py

Step 3: Classify an article into IPTC L2 subcategories (multi-label) using BM25.
- Loads nested IPTC taxonomy JSON: categories(L1) -> subcategories(L2)
- Builds a BM25 index over L2 "profiles" (label + definition + seed anchors)
- Builds a query from title + (optional) extracted anchors + body text
- Returns top-k L2 with scores and derived L1 set

Dependencies:
  pip install rank-bm25

Usage examples:
  python backend/tools/bm25_classify.py \
    --taxonomy shared/taxonomy.json \
    --lang en \
    --title "Mark Carney Takes On Donald Trump and Emerges as a Global Political Star" \
    --in article.txt \
    --topk 10 \
    --max-labels 3 \
    --within-best 0.85

  # Using anchors extracted in step 2 (extract_anchors.py):
  python backend/tools/bm25_classify.py \
    --taxonomy shared/taxonomy.json \
    --lang en \
    --title "Mark Carney Takes On Donald Trump and Emerges as a Global Political Star" \
    --in article.txt \
    --anchors-json anchors.json \
    --anchors-top 25 \
    --topk 10 \
    --max-labels 3 \
    --within-best 0.85
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi


# -----------------------------
# Tokenization / normalization
# -----------------------------
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
    "sera","seront","était","étaient","près","vers","chez"
}

def tokenize(text: str, lang: str) -> List[str]:
    text = text.lower()
    toks = WORD_RE.findall(text)
    stop = STOP_EN if lang == "en" else STOP_FR
    return [t for t in toks if t not in stop and len(t) > 2]


# -----------------------------
# Taxonomy loading
# -----------------------------
@dataclass
class L2Node:
    l2_id: str
    l2_label: str
    l1_id: str
    l1_label: str
    profile_text: str

def best_lang_value(d: Dict, lang: str, fallback_lang: str = "en") -> str:
    if not isinstance(d, dict):
        return ""
    v = d.get(lang)
    if v and v.strip():
        return v.strip()
    v = d.get(fallback_lang)
    return (v or "").strip()

def build_l2_nodes(taxonomy: dict, lang: str) -> List[L2Node]:
    nodes: List[L2Node] = []

    categories = taxonomy.get("categories") or []
    for l1 in categories:
        l1_id = l1.get("id", "")
        l1_label = best_lang_value(l1.get("labels", {}), lang) or l1_id

        for l2 in l1.get("subcategories", []) or []:
            l2_id = l2.get("id", "")
            l2_label = best_lang_value(l2.get("labels", {}), lang) or l2_id

            definition = best_lang_value(l2.get("definitions", {}), lang)
            anchors = l2.get("anchors", {})
            anchors_list = []
            if isinstance(anchors, dict):
                anchors_list = anchors.get(lang) or anchors.get("en") or []
            anchors_list = [a for a in anchors_list if isinstance(a, str) and a.strip()]

            # L2 profile: label + definition + anchors (lexical model)
            parts = [l2_label]
            if definition:
                parts.append(definition)
            if anchors_list:
                parts.extend(anchors_list)

            profile_text = " ".join(parts)

            nodes.append(L2Node(
                l2_id=l2_id,
                l2_label=l2_label,
                l1_id=l1_id,
                l1_label=l1_label,
                profile_text=profile_text
            ))

    return nodes


# -----------------------------
# Query building (title + anchors + body)
# -----------------------------
def load_text(path: Optional[str]) -> str:
    if not path:
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_anchors(anchors_json_path: Optional[str]) -> List[str]:
    if not anchors_json_path:
        return []
    with open(anchors_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    anchors = data.get("anchors", [])
    phrases = []
    for a in anchors:
        if isinstance(a, dict) and "phrase" in a:
            phrases.append(a["phrase"])
        elif isinstance(a, str):
            phrases.append(a)
    return [p for p in phrases if isinstance(p, str) and p.strip()]

def build_query(
    title: str,
    body: str,
    lang: str,
    anchor_phrases: List[str],
    anchors_top: int,
    body_terms_cap: int
) -> str:
    # Weight title by repetition (BM25 is term-frequency sensitive)
    title = (title or "").strip()
    body = (body or "").strip()

    top_anchors = [p.strip() for p in anchor_phrases[:anchors_top] if p.strip()]

    # Light lexical body contribution: keep first N tokens (already cleaned upstream)
    body_tokens = tokenize(body, lang)[:body_terms_cap]
    body_snippet = " ".join(body_tokens)

    # Query: title x2 + anchors + snippet
    query = " ".join(
        ([title] * 2 if title else []) +
        top_anchors +
        ([body_snippet] if body_snippet else [])
    ).strip()

    return query


# -----------------------------
# Multi-label selection
# -----------------------------
def select_labels(
    scored: List[Tuple[L2Node, float]],
    topk: int,
    max_labels: int,
    min_score: float,
    within_best: float
) -> List[Tuple[L2Node, float]]:
    """
    BM25 scores are unbounded; use:
      - absolute floor (min_score)
      - relative threshold (within_best * best_score)
      - cap labels
    """
    if not scored:
        return []

    scored = scored[:topk]
    best_score = scored[0][1]
    rel_floor = best_score * within_best

    chosen = []
    for node, s in scored:
        if s < min_score:
            continue
        if s < rel_floor:
            continue
        chosen.append((node, s))
        if len(chosen) >= max_labels:
            break
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True, help="Nested IPTC taxonomy JSON (categories->subcategories).")
    ap.add_argument("--lang", choices=["en", "fr"], required=True, help="Article language for lexical BM25.")
    ap.add_argument("--title", default="", help="Article title (recommended).")
    ap.add_argument("--in", dest="in_path", default=None, help="Article body text file (default: stdin).")

    ap.add_argument("--anchors-json", default=None, help="Anchors JSON from extract_anchors.py (optional).")
    ap.add_argument("--anchors-top", type=int, default=25, help="How many extracted anchor phrases to include in query.")

    ap.add_argument("--topk", type=int, default=10, help="How many L2 candidates to score/print.")
    ap.add_argument("--max-labels", type=int, default=3, help="Max L2 labels to return (multi-label).")
    ap.add_argument("--min-score", type=float, default=2.0, help="Absolute BM25 floor (tune on your corpus).")
    ap.add_argument("--within-best", type=float, default=0.85, help="Keep labels with score >= within_best*best.")

    ap.add_argument("--body-terms-cap", type=int, default=200, help="Max number of body tokens used in query.")
    ap.add_argument("--json-out", default=None, help="Write output JSON to file (default: stdout).")
    args = ap.parse_args()

    with open(args.taxonomy, "r", encoding="utf-8") as f:
        tax = json.load(f)

    l2_nodes = build_l2_nodes(tax, args.lang)
    if not l2_nodes:
        raise SystemExit("No L2 nodes found in taxonomy. Check schema: categories[].subcategories[]")

    corpus_tokens = [tokenize(n.profile_text, args.lang) for n in l2_nodes]
    bm25 = BM25Okapi(corpus_tokens)

    body = load_text(args.in_path)
    anchors = load_anchors(args.anchors_json)

    query = build_query(
        title=args.title,
        body=body,
        lang=args.lang,
        anchor_phrases=anchors,
        anchors_top=args.anchors_top,
        body_terms_cap=args.body_terms_cap
    )
    query_tokens = tokenize(query, args.lang)

    scores = bm25.get_scores(query_tokens)
    ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    scored = [(l2_nodes[i], float(scores[i])) for i in ranked_idx]
    top_scored = scored[:args.topk]

    chosen = select_labels(
        scored=top_scored,
        topk=args.topk,
        max_labels=args.max_labels,
        min_score=args.min_score,
        within_best=args.within_best
    )

    # Derived L1 set from chosen L2s
    l1_map: Dict[str, str] = {}
    for node, _ in chosen:
        l1_map[node.l1_id] = node.l1_label

    payload = {
        "lang": args.lang,
        "query_preview": query[:3000],
        "selected": [
            {
                "l2_id": n.l2_id,
                "l2_label": n.l2_label,
                "score": s,
                "l1_id": n.l1_id,
                "l1_label": n.l1_label
            } for n, s in chosen
        ],
        "derived_l1": [{"l1_id": k, "l1_label": v} for k, v in l1_map.items()],
        "top_candidates": [
            {
                "l2_id": n.l2_id,
                "l2_label": n.l2_label,
                "score": s,
                "l1_id": n.l1_id,
                "l1_label": n.l1_label
            } for n, s in top_scored
        ],
        "thresholds": {
            "min_score": args.min_score,
            "within_best": args.within_best,
            "max_labels": args.max_labels
        }
    }

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    else:
        print(out)


if __name__ == "__main__":
    main()