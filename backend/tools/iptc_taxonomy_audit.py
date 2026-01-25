#!/usr/bin/env python3
"""
iptc_taxonomy_audit.py

Audit an IPTC L1/L2 taxonomy JSON in your Lumen format:
{
  "categories": [
    {
      "id": "...",
      "labels": {"en": "...", "fr": "..."},
      "definitions": {"en": "...", "fr": "..."},
      "subcategories": [
        { "id": "...", "parent_id": "...", "labels": {...}, "definitions": {...}, ... }
      ]
    }
  ]
}

Outputs:
- Summary to stdout
- Optional CSV with flagged nodes (missing labels/defs, fr==en, likely wrong language, retired/deprecated)

Usage:
  python backend/tools/iptc_taxonomy_audit.py \
    --taxonomy shared/iptc_l1l2_full.json \
    --out-csv out/taxonomy_audit.csv
"""

import argparse
import csv
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

FR_FUNCTION_WORDS = {
    "le","la","les","de","des","du","un","une","et","ou","dans","en","sur","pour","par","avec","sans",
    "toutes","tous","toute","toutes","formes","concernant","ainsi","ainsi","droit","droits","santé",
    "économie","gouvernement","politique","société","travail","environnement","culture","médias"
}

EN_FUNCTION_WORDS = {
    "the","of","and","or","in","on","for","by","with","without","all","forms","matters","concerning",
    "society","government","politics","economy","environment","culture","media","health","education","science"
}

def norm(s: Optional[str]) -> str:
    return (s or "").strip()

def get(d: Dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def looks_retired(text: str) -> bool:
    t = (text or "").lower()
    return "(retired)" in t or "retired" == t.strip()

def tokenize_words(s: str) -> List[str]:
    return re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ']+", s.lower())

def lang_hint_score(text: str) -> Tuple[int, int]:
    """
    Returns (fr_score, en_score) based on presence of common function words.
    Very lightweight heuristic; not a detector, just a flag.
    """
    toks = tokenize_words(text)
    fr = sum(1 for t in toks if t in FR_FUNCTION_WORDS)
    en = sum(1 for t in toks if t in EN_FUNCTION_WORDS)
    return fr, en

@dataclass
class Row:
    level: str
    id: str
    parent_id: str
    label_en: str
    label_fr: str
    def_en: str
    def_fr: str
    flags: str

def iter_nodes(tax: Dict[str, Any]):
    for l1 in tax.get("categories", []) or []:
        yield ("L1", l1, None)
        for l2 in l1.get("subcategories", []) or []:
            yield ("L2", l2, l1)

def compute_audit(tax: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Row]]:
    counts = {
        "l1": 0,
        "l2": 0,
        "label_en_present": 0,
        "label_fr_present": 0,
        "def_en_present": 0,
        "def_fr_present": 0,
        "label_en_missing": 0,
        "label_fr_missing": 0,
        "def_en_missing": 0,
        "def_fr_missing": 0,
        "retired_or_deprecated": 0,
        "fr_equals_en_label": 0,
        "fr_equals_en_def": 0,
        "fr_looks_english": 0,
        "en_looks_french": 0,
    }

    rows: List[Row] = []

    for level, node, parent in iter_nodes(tax):
        if level == "L1":
            counts["l1"] += 1
            parent_id = ""
        else:
            counts["l2"] += 1
            parent_id = get(node, "parent_id", default="") or (get(parent, "id", default="") if parent else "")

        nid = get(node, "id", default="")
        labels = get(node, "labels", default={}) or {}
        defs = get(node, "definitions", default={}) or {}

        label_en = norm(labels.get("en"))
        label_fr = norm(labels.get("fr"))
        def_en = norm(defs.get("en"))
        def_fr = norm(defs.get("fr"))

        flags = []

        # Presence coverage
        if label_en:
            counts["label_en_present"] += 1
        else:
            counts["label_en_missing"] += 1
            flags.append("missing_label_en")

        if label_fr:
            counts["label_fr_present"] += 1
        else:
            counts["label_fr_missing"] += 1
            flags.append("missing_label_fr")

        if def_en:
            counts["def_en_present"] += 1
        else:
            counts["def_en_missing"] += 1
            flags.append("missing_def_en")

        if def_fr:
            counts["def_fr_present"] += 1
        else:
            counts["def_fr_missing"] += 1
            flags.append("missing_def_fr")

        # Equality checks
        if label_en and label_fr and label_en == label_fr:
            counts["fr_equals_en_label"] += 1
            flags.append("label_fr_equals_en")

        if def_en and def_fr and def_en == def_fr:
            counts["fr_equals_en_def"] += 1
            flags.append("def_fr_equals_en")

        # Retired/deprecated checks (best-effort)
        deprecated = bool(get(node, "deprecated", default=False))
        if deprecated or looks_retired(label_en) or looks_retired(label_fr):
            counts["retired_or_deprecated"] += 1
            flags.append("retired_or_deprecated")

        # Language sanity heuristics (only meaningful if text exists)
        if label_fr:
            frs, ens = lang_hint_score(label_fr)
            # If FR label has more EN function words than FR ones, flag
            if ens >= 2 and ens > frs:
                counts["fr_looks_english"] += 1
                flags.append("fr_label_looks_en")

        if def_fr:
            frs, ens = lang_hint_score(def_fr)
            if ens >= 3 and ens > frs:
                counts["fr_looks_english"] += 1
                flags.append("fr_def_looks_en")

        if label_en:
            frs, ens = lang_hint_score(label_en)
            if frs >= 2 and frs > ens:
                counts["en_looks_french"] += 1
                flags.append("en_label_looks_fr")

        if def_en:
            frs, ens = lang_hint_score(def_en)
            if frs >= 3 and frs > ens:
                counts["en_looks_french"] += 1
                flags.append("en_def_looks_fr")

        # Cross-field mismatch hints
        if label_en and not label_fr:
            flags.append("fr_missing_en_present")
        if label_fr and not label_en:
            flags.append("en_missing_fr_present")
        if def_en and not def_fr:
            flags.append("fr_def_missing_en_present")
        if def_fr and not def_en:
            flags.append("en_def_missing_fr_present")

        if flags:
            rows.append(Row(
                level=level,
                id=nid,
                parent_id=parent_id or "",
                label_en=label_en,
                label_fr=label_fr,
                def_en=def_en,
                def_fr=def_fr,
                flags=";".join(flags),
            ))

    totals = counts["l1"] + counts["l2"]
    summary = {
        "counts": counts,
        "totals": {
            "nodes_total": totals,
            "l1": counts["l1"],
            "l2": counts["l2"],
        },
        "coverage": {
            "labels.en_pct": round(100 * counts["label_en_present"] / max(1, totals), 2),
            "labels.fr_pct": round(100 * counts["label_fr_present"] / max(1, totals), 2),
            "definitions.en_pct": round(100 * counts["def_en_present"] / max(1, totals), 2),
            "definitions.fr_pct": round(100 * counts["def_fr_present"] / max(1, totals), 2),
        }
    }
    return summary, rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True, help="Path to iptc_l1l2_full.json")
    ap.add_argument("--out-csv", default=None, help="Write flagged rows to CSV")
    ap.add_argument("--max-print", type=int, default=25, help="Max flagged examples to print")
    args = ap.parse_args()

    with open(args.taxonomy, "r", encoding="utf-8") as f:
        tax = json.load(f)

    summary, rows = compute_audit(tax)

    counts = summary["counts"]
    cov = summary["coverage"]
    totals = summary["totals"]["nodes_total"]

    print("=== IPTC Taxonomy Audit ===")
    print(f"Nodes: total={totals}  L1={summary['totals']['l1']}  L2={summary['totals']['l2']}")
    print("Coverage:")
    print(f"  labels.en: {cov['labels.en_pct']}%  ({counts['label_en_present']}/{totals})")
    print(f"  labels.fr: {cov['labels.fr_pct']}%  ({counts['label_fr_present']}/{totals})")
    print(f"  defs.en  : {cov['definitions.en_pct']}%  ({counts['def_en_present']}/{totals})")
    print(f"  defs.fr  : {cov['definitions.fr_pct']}%  ({counts['def_fr_present']}/{totals})")
    print("Flags:")
    print(f"  retired/deprecated: {counts['retired_or_deprecated']}")
    print(f"  fr==en (label):     {counts['fr_equals_en_label']}")
    print(f"  fr==en (def):       {counts['fr_equals_en_def']}")
    print(f"  fr looks EN:        {counts['fr_looks_english']}")
    print(f"  en looks FR:        {counts['en_looks_french']}")

    if rows:
        print(f"\nFlagged nodes: {len(rows)} (showing up to {args.max_print})")
        for r in rows[:args.max_print]:
            print(f"- {r.level} {r.id} parent={r.parent_id} flags={r.flags} en='{r.label_en}' fr='{r.label_fr}'")
    else:
        print("\nNo flagged nodes.")

    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["level","id","parent_id","flags","label_en","label_fr","def_en","def_fr"])
            for r in rows:
                w.writerow([r.level, r.id, r.parent_id, r.flags, r.label_en, r.label_fr, r.def_en, r.def_fr])
        print(f"\nWrote CSV: {args.out_csv}")

if __name__ == "__main__":
    main()