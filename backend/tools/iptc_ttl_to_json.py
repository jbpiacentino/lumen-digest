#!/usr/bin/env python3
"""
iptc_ttl_to_json.py

Convert IPTC Media Topics SKOS Turtle files (EN + FR) into JSON.

Outputs either:
- nested L1/L2 JSON: categories[] (L1) -> subcategories[] (L2)
- or flat JSON list with broader links
"""

import argparse
import json
from collections import defaultdict
from typing import Dict, List, Optional

from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, SKOS, OWL, DCTERMS

ID_PREFIX = "medtop:"

# Accept both http and https, and require an 8-digit concept code
MEDTOP_URI_RE = r"^https?://cv\.iptc\.org/newscodes/mediatopic/(\d{8})/?$"


def concept_id_from_uri(uri: URIRef) -> Optional[str]:
    s = str(uri).strip()
    # accept both http and https
    s = s.replace("https://", "http://", 1) if s.startswith("https://cv.iptc.org/") else s
    if not s.startswith("http://cv.iptc.org/newscodes/mediatopic/"):
        return None
    tail = s.split("http://cv.iptc.org/newscodes/mediatopic/", 1)[1].strip("/")
    if not tail:
        return None
    # keep only numeric concept codes
    if not tail.isdigit():
        return None
    # Media Topics are 8-digit numeric IDs; if you want to be permissive, remove this length check
    if len(tail) != 8:
        return None
    return f"medtop:{tail}"


def load_graph(ttl_path: str) -> Graph:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return g


def norm_lang(lang: str) -> str:
    """
    Normalize BCP47 tags to base language: en-GB -> en, fr-FR -> fr.
    Keeps unknown tags as-is.
    """
    lang = (lang or "").strip()
    if not lang:
        return ""
    return lang.split("-")[0].lower()


def pick_lang_literals(lits: List[Literal]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for lit in lits:
        if not isinstance(lit, Literal):
            continue
        txt = str(lit).strip()
        if not txt:
            continue
        lang = norm_lang(lit.language or "")
        if lang:
            out.setdefault(lang, txt)
    return out


def get_literals(g: Graph, subj: URIRef, pred: URIRef) -> List[Literal]:
    return [o for o in g.objects(subj, pred) if isinstance(o, Literal)]


def get_uris(g: Graph, subj: URIRef, pred: URIRef) -> List[URIRef]:
    return [o for o in g.objects(subj, pred) if isinstance(o, URIRef)]


def is_deprecated(g: Graph, subj: URIRef) -> bool:
    for o in g.objects(subj, OWL.deprecated):
        if isinstance(o, Literal) and str(o).lower() in ("true", "1"):
            return True
    return False


def replaced_by(g: Graph, subj: URIRef) -> List[str]:
    out = []
    for o in g.objects(subj, DCTERMS.isReplacedBy):
        if isinstance(o, URIRef):
            cid = concept_id_from_uri(o)
            if cid:
                out.append(cid)
    return out


def build_concepts(g: Graph) -> Dict[str, dict]:
    concepts: Dict[str, dict] = {}

    for subj in g.subjects(RDF.type, SKOS.Concept):
        cid = concept_id_from_uri(subj)
        if not cid:
            continue

        labels = pick_lang_literals(get_literals(g, subj, SKOS.prefLabel))
        defs = pick_lang_literals(get_literals(g, subj, SKOS.definition))

        broader = []
        for b in get_uris(g, subj, SKOS.broader):
            bid = concept_id_from_uri(b)
            if bid:
                broader.append(bid)

        data = concepts.get(cid, {
            "id": cid,
            "uri": str(subj),
            "labels": {},
            "definitions": {},
            "broader": [],
            "deprecated": False,
            "replaced_by": [],
        })

        data["labels"].update(labels)
        data["definitions"].update(defs)

        if broader:
            existing = set(data["broader"])
            for b in broader:
                if b not in existing:
                    data["broader"].append(b)

        data["deprecated"] = data["deprecated"] or is_deprecated(g, subj)

        rb = replaced_by(g, subj)
        if rb:
            existing_rb = set(data["replaced_by"])
            for x in rb:
                if x not in existing_rb:
                    data["replaced_by"].append(x)

        concepts[cid] = data

    return concepts


def merge_concepts(a: Dict[str, dict], b: Dict[str, dict]) -> Dict[str, dict]:
    out = dict(a)
    for cid, d in b.items():
        if cid not in out:
            out[cid] = d
            continue
        out[cid]["labels"].update(d.get("labels", {}))
        out[cid]["definitions"].update(d.get("definitions", {}))

        existing = set(out[cid].get("broader", []))
        for br in d.get("broader", []):
            if br not in existing:
                out[cid].setdefault("broader", []).append(br)

        out[cid]["deprecated"] = out[cid].get("deprecated", False) or d.get("deprecated", False)

        existing_rb = set(out[cid].get("replaced_by", []))
        for rb in d.get("replaced_by", []):
            if rb not in existing_rb:
                out[cid].setdefault("replaced_by", []).append(rb)
    return out


def build_children_index(concepts: Dict[str, dict]) -> Dict[str, List[str]]:
    children = defaultdict(list)
    for cid, d in concepts.items():
        for parent in d.get("broader", []):
            children[parent].append(cid)
    return children


def to_l1l2(concepts: Dict[str, dict]) -> dict:
    children = build_children_index(concepts)

    # L1 roots = concepts with no broader
    roots = sorted([cid for cid, d in concepts.items() if not d.get("broader")])

    categories = []
    for l1_id in roots:
        l1 = concepts[l1_id]
        if l1.get("deprecated"):
            continue

        l1_obj = {
            "id": l1_id,
            "labels": {
                "en": l1.get("labels", {}).get("en") or l1_id,
                "fr": l1.get("labels", {}).get("fr") or l1.get("labels", {}).get("en") or l1_id,
            },
            "definitions": {
                "en": l1.get("definitions", {}).get("en", ""),
                "fr": l1.get("definitions", {}).get("fr", "") or "",
            },
            "subcategories": []
        }

        # L2 = immediate children of L1
        l2_ids = sorted(children.get(l1_id, []))
        for l2_id in l2_ids:
            l2 = concepts.get(l2_id, {})
            if not l2 or l2.get("deprecated"):
                continue

            l2_obj = {
                "id": l2_id,
                "parent_id": l1_id,
                "labels": {
                    "en": l2.get("labels", {}).get("en") or l2_id,
                    "fr": l2.get("labels", {}).get("fr") or l2.get("labels", {}).get("en") or l2_id,
                },
                "definitions": {
                    "en": l2.get("definitions", {}).get("en", ""),
                    "fr": l2.get("definitions", {}).get("fr", "") or "",
                },
                "anchors": {"en": [], "fr": []}
            }
            l1_obj["subcategories"].append(l2_obj)

        categories.append(l1_obj)

    return {
        "version": "iptc_full_l1l2_import_v1",
        "source": "IPTC Media Topics (SKOS Turtle import)",
        "categories": categories
    }


def to_flat(concepts: Dict[str, dict]) -> dict:
    items = []
    for cid in sorted(concepts.keys()):
        d = concepts[cid]
        items.append({
            "id": cid,
            "uri": d.get("uri"),
            "labels": d.get("labels", {}),
            "definitions": d.get("definitions", {}),
            "broader": d.get("broader", []),
            "deprecated": bool(d.get("deprecated", False)),
            "replaced_by": d.get("replaced_by", []),
        })
    return {
        "version": "iptc_full_flat_import_v1",
        "source": "IPTC Media Topics (SKOS Turtle import)",
        "concepts": items
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttl-en", required=True)
    ap.add_argument("--ttl-fr", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["l1l2", "flat"], default="l1l2")
    args = ap.parse_args()

    g_en = load_graph(args.ttl_en)
    g_fr = load_graph(args.ttl_fr)

    c_en = build_concepts(g_en)
    c_fr = build_concepts(g_fr)
    concepts = merge_concepts(c_en, c_fr)

    out = to_l1l2(concepts) if args.mode == "l1l2" else to_flat(concepts)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.mode} JSON to {args.out}")
    print(f"Concepts parsed: {len(concepts)}")


if __name__ == "__main__":
    main()