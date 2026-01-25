#!/usr/bin/env python3
import argparse, json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--patch", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--replace", action="store_true", help="Replace anchors[lang] instead of extending")
    args = ap.parse_args()

    tax = json.load(open(args.taxonomy, "r", encoding="utf-8"))
    patch = json.load(open(args.patch, "r", encoding="utf-8"))
    lang = patch["lang"]
    anchors_map = patch["anchors"]

    # Taxonomy format: { categories: [ {id, labels, definitions, subcategories...} ] }
    cats = tax.get("categories", [])
    updated = 0

    for c in cats:
        cid = c.get("id")
        if cid in anchors_map:
            c.setdefault("anchors", {}).setdefault(lang, [])
            if args.replace:
                c["anchors"][lang] = anchors_map[cid]
            else:
                existing = list(c["anchors"][lang])
                seen = set(existing)
                for a in anchors_map[cid]:
                    if a not in seen:
                        existing.append(a)
                        seen.add(a)
                c["anchors"][lang] = existing
            updated += 1

    json.dump(tax, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Updated L1 nodes: {updated} (lang={lang})")
    print(f"Wrote: {args.out}")

if __name__ == "__main__":
    main()