import re
from collections import Counter
from typing import Dict, List

from rank_bm25 import BM25Okapi

from .article_cleaning import clean_text_rules


WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]*")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]\s+")

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

GENERIC_DENY_EN = {"world","people","issue","issues","action","actions","group","groups","system","systems",
                   "general","public","national","international","report","reports","news","today","said","says"}
GENERIC_DENY_FR = {"monde","gens","personnes","question","questions","action","actions","groupe","groupes",
                   "système","systèmes","général","publique","national","internationale","rapport","rapports",
                   "actualités","aujourd'hui"}

DENY_TOKENS = {
    "https","http","www","com","html","htm","php","asp",
    "nytimes","wsj","ft","bloomberg","reuters","apnews","cnn","bbc",
    "advertisement","subscribe","subscription","newsletter","sign","signup","sign-up","gift",
    "read","more","cookie","cookies","privacy","terms","share","link",
    "facebook","twitter","instagram","tiktok","youtube",
    "after-bottom","afterbottom","before-bottom","beforebottom",
    "verified"
}

DENY_PHRASE_RE = re.compile(
    r"(after-bottom|before-bottom|continue reading|sign up|newsletter|advertisement|subscribe|subscription)",
    re.I
)


def tokenize(text: str, lang: str) -> List[str]:
    text = (text or "").lower()
    toks = WORD_RE.findall(text)
    stop = STOP_EN if lang == "en" else STOP_FR
    return [t for t in toks if t not in stop and len(t) > 2]


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
    if DENY_PHRASE_RE.search(phrase):
        return False
    if any(t in DENY_TOKENS for t in phrase_toks):
        return False
    if lang == "en" and any(len(t) == 1 for t in phrase_toks):
        return False
    if len(phrase_toks) == 1:
        t = phrase_toks[0]
        return t.isalpha() and len(t) >= 6
    return True


def ngrams_from_tokens(toks: List[str], max_ngram: int):
    n = len(toks)
    for k in range(1, max_ngram + 1):
        if k > n:
            break
        for i in range(0, n - k + 1):
            yield tuple(toks[i:i+k])


def extract_anchors_bm25(
    text: str,
    lang: str,
    topk: int = 30,
    max_ngram: int = 3,
    min_chars: int = 4,
) -> Dict:
    cleaned = clean_text_rules(text or "")
    if not cleaned:
        return {"cleaned_text": "", "anchors": []}

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]
    if not sentences:
        sentences = [cleaned]

    corpus_tokens = [tokenize(sentence, lang) for sentence in sentences if sentence]
    corpus_tokens = [toks for toks in corpus_tokens if toks]
    if not corpus_tokens:
        return {"cleaned_text": cleaned, "anchors": []}

    bm25 = BM25Okapi(corpus_tokens)

    tokens_flat = tokenize(cleaned, lang)
    freq = Counter(tokens_flat)

    candidate_counts = Counter()
    for ng in ngrams_from_tokens(tokens_flat, max_ngram):
        if not valid_phrase(list(ng), lang, min_chars):
            continue
        candidate_counts[" ".join(ng)] += 1

    anchors = []
    for phrase, count in candidate_counts.items():
        q_tokens = tokenize(phrase, lang)
        if not q_tokens:
            continue
        scores = bm25.get_scores(q_tokens)
        score = float(max(scores)) if scores is not None else 0.0
        anchors.append({
            "phrase": phrase,
            "score": score,
            "count": int(count),
        })

    anchors.sort(key=lambda a: (-a["score"], -a["count"], a["phrase"]))
    return {
        "cleaned_text": cleaned,
        "anchors": anchors[:topk],
    }


def add_presence_counts(anchors: List[Dict], taxonomy: dict, lang: str) -> List[Dict]:
    if not anchors or not taxonomy:
        return anchors

    def normalize_phrase(text: str) -> str:
        return " ".join((text or "").lower().split())

    anchor_map = {}
    categories = taxonomy.get("categories") or []
    for category in categories:
        for node in [category] + (category.get("subcategories") or []):
            anchors_data = node.get("anchors", {})
            if isinstance(anchors_data, dict):
                anchors_list = anchors_data.get(lang) or anchors_data.get("en") or []
            else:
                anchors_list = anchors_data or []
            for phrase in anchors_list:
                key = normalize_phrase(phrase)
                if not key:
                    continue
                anchor_map[key] = anchor_map.get(key, 0) + 1

    for anchor in anchors:
        key = normalize_phrase(anchor.get("phrase"))
        anchor["presence_count"] = anchor_map.get(key, 0)
    return anchors
