#!/usr/bin/env python3
"""
extract_anchors.py

Step 2: Extract anchors/keyphrases from a full-text article (no LLMs).
- YAKE keyphrase extraction (single-document, unsupervised).
- Normalization + boilerplate filtering + dedup + preference for multi-word.
- EN/FR support via stopword lists.

Install:
  pip install yake

Usage:
  python extract_anchors.py --lang en --topk 40 --max-ngram 3 --in article.txt
  cat article.txt | python extract_anchors.py --lang fr --topk 50

Output:
  JSON with anchors (best-first), each containing phrase + score + normalized form.
  Note: YAKE scores -> lower is better.
"""

import argparse
import json
import re
import sys
import unicodedata
from typing import List, Tuple, Dict, Optional

import yake


# -----------------------------
# Minimal stopwords (extend as needed)
# -----------------------------
STOPWORDS_EN = {
    "a","an","and","are","as","at","be","but","by","for","from","has","have","he","her","his","i",
    "in","into","is","it","its","of","on","or","that","the","their","they","this","to","was","were",
    "will","with","you","your","we","our","not","than","then","so","if","about","after","before",
    "over","under","between","because","also","more","most","can","could","should","would"
}

STOPWORDS_FR = {
    "un","une","des","et","ou","à","au","aux","de","du","des","dans","en","sur","pour","par","avec",
    "sans","ce","ces","cet","cette","qui","que","quoi","dont","où","il","elle","ils","elles","on","nous",
    "vous","je","tu","me","te","se","lui","leur","les","la","le","l","d","c","n","ne","pas","plus",
    "moins","comme","mais","donc","or","ni","car","ainsi","été","être","avait","ont","a","est","sont",
    "sera","seront","était","étaient","dans","près","vers","chez"
}


# -----------------------------
# Boilerplate / noise phrases
# -----------------------------
NOISE_PHRASES = {
    "read more",
    "sign up",
    "newsletter",
    "privacy policy",
    "terms of service",
    "cookie policy",
    "cookies",
    "advertisement",
    "skip advertisement",
    "click here",
    "all rights reserved",
}


# -----------------------------
# Normalization helpers
# -----------------------------
WS_RE = re.compile(r"\s+")
PUNCT_EDGE_RE = re.compile(r"^[\W_]+|[\W_]+$")

def strip_accents(s: str) -> str:
    # Keep accents by default, but you may want to normalize for dedup keys.
    # This function removes diacritics deterministically (no AI).
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def normalize_phrase(phrase: str) -> str:
    p = phrase.strip()
    p = WS_RE.sub(" ", p)
    p = PUNCT_EDGE_RE.sub("", p)
    return p.strip()

def norm_key(phrase: str) -> str:
    # canonical dedup key: lowercase + deaccent + collapse spaces
    p = strip_accents(phrase.lower())
    p = WS_RE.sub(" ", p)
    p = PUNCT_EDGE_RE.sub("", p)
    return p.strip()


# -----------------------------
# Filters
# -----------------------------
def looks_like_noise(phrase: str) -> bool:
    k = norm_key(phrase)
    if not k:
        return True
    if k in NOISE_PHRASES:
        return True
    # avoid very short / non-informative
    if len(k) < 3:
        return True
    # mostly digits / punctuation
    alpha = sum(ch.isalpha() for ch in k)
    if alpha == 0:
        return True
    return False

def boundary_stopword_filter(phrase: str, stopwords: set) -> bool:
    """
    Reject phrases that start or end with stopwords (common issue in keyphrase extraction).
    """
    tokens = phrase.lower().split()
    if not tokens:
        return False
    if tokens[0] in stopwords or tokens[-1] in stopwords:
        return True
    # also reject if phrase is entirely stopwords
    if all(t in stopwords for t in tokens):
        return True
    return False

def prefer_multiword(phrase: str) -> int:
    """
    Higher is better. We’ll rank multi-word phrases ahead when scores are close.
    """
    return 1 if len(phrase.split()) >= 2 else 0


# -----------------------------
# Anchor extraction (YAKE + filtering)
# -----------------------------
def extract_anchors(
    text: str,
    lang: str,
    topk: int = 40,
    max_ngram: int = 3,
    dedup_lim: float = 0.9,
    overgenerate_factor: int = 3,
) -> List[Dict]:
    stopwords = STOPWORDS_EN if lang == "en" else STOPWORDS_FR

    # YAKE expects ISO-ish language codes, "en" and "fr" are fine
    kw = yake.KeywordExtractor(
        lan=lang,
        n=max_ngram,
        top=topk * overgenerate_factor,
        dedupLim=dedup_lim,
        features=None,
    )

    raw: List[Tuple[str, float]] = kw.extract_keywords(text)

    out: List[Dict] = []
    seen = set()

    for phrase, score in raw:
        p = normalize_phrase(phrase)
        if not p:
            continue
        if looks_like_noise(p):
            continue
        if boundary_stopword_filter(p, stopwords):
            continue

        k = norm_key(p)
        if k in seen:
            continue
        seen.add(k)

        out.append({
            "phrase": p,
            "score": float(score),          # YAKE: lower is better
            "key": k,
            "multiword": len(p.split()) >= 2
        })

        if len(out) >= topk:
            break

    # Sorting: YAKE score ascending, then prefer multi-word if scores tie-ish
    # We keep YAKE as primary signal.
    out.sort(key=lambda d: (d["score"], -int(d["multiword"]), d["key"]))
    return out[:topk]


def read_input(path: Optional[str]) -> str:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["en", "fr"], required=True, help="Language for YAKE + stopwords.")
    ap.add_argument("--topk", type=int, default=40, help="Number of anchors to keep.")
    ap.add_argument("--max-ngram", type=int, default=3, help="Max n-gram length for YAKE (1..3 typical).")
    ap.add_argument("--dedup-lim", type=float, default=0.9, help="YAKE dedup threshold (0..1).")
    ap.add_argument("--in", dest="in_path", default=None, help="Input text file (default: stdin).")
    ap.add_argument("--json", dest="json_path", default=None, help="Write JSON to file (default: stdout).")
    args = ap.parse_args()

    text = read_input(args.in_path)
    text = WS_RE.sub(" ", text).strip()

    anchors = extract_anchors(
        text=text,
        lang=args.lang,
        topk=args.topk,
        max_ngram=args.max_ngram,
        dedup_lim=args.dedup_lim,
    )

    payload = {
        "lang": args.lang,
        "topk": args.topk,
        "max_ngram": args.max_ngram,
        "anchors": anchors
    }

    js = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            f.write(js + "\n")
    else:
        print(js)


if __name__ == "__main__":
    main()