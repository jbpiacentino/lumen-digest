#!/usr/bin/env python3
"""
clean_article.py

Goal: produce "BM25-safe" clean text from either:
  - URL
  - raw HTML
  - already-extracted plaintext/markdown

Uses Trafilatura for HTML -> main content extraction (no LLM, deterministic),
then applies regex/rule-based cleanup to reduce lexical noise:
  - remove URLs, image lines, markdown links, boilerplate, ads
  - optional cutoff at a heading (e.g. "## Trans Canada")
  - optional removal of low-signal lines

Install:
  pip install trafilatura

Usage:
  # 1) Clean from URL (best): fetch + extract + clean
  python backend/tools/clean_article.py --url "https://www.nytimes.com/2026/01/24/world/canada/carney-trump-us-greenland.html" --out cleaned.txt

  # 2) Clean from HTML file
  python backend/tools/clean_article.py --in article.html --html --out cleaned.txt

  # 3) Clean from extracted markdown/text (no trafilatura stage)
  python backend/tools/clean_article.py --in article.txt --out cleaned.txt

  # 4) Cut off at a heading to drop newsletter roundups:
  python backend/tools/clean_article.py --in article.txt --cut-after-heading "## Trans Canada" --out cleaned.txt
"""

import argparse
import re
import sys
from typing import Optional, Tuple  
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import trafilatura


# -----------------------------
# Regex patterns: remove noise that distorts lexical matching
# -----------------------------
RE_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")                 # ![alt](url)
RE_URL = re.compile(r"https?://\S+")
RE_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")                # [text](url) -> text
RE_BRACKETED_READ = re.compile(r"^\s*\[\*?(read|from opinion)\b.*$", re.IGNORECASE)
RE_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
RE_AD = re.compile(r"^\s*(advertisement|skip advertisement)\s*$", re.IGNORECASE)

# Common newsletter boilerplate / calls-to-action (extend as you observe)
BOILERPLATE_LINE_PATTERNS = [
    re.compile(r"^\s*how are we doing\?\s*$", re.IGNORECASE),
    re.compile(r"^\s*like this email\?\s*$", re.IGNORECASE),
    re.compile(r"^\s*forward it to your friends.*$", re.IGNORECASE),
    re.compile(r"^\s*sign up here.*$", re.IGNORECASE),
    re.compile(r"^\s*related content\s*$", re.IGNORECASE),
    re.compile(r"^\s*we're eager to have your thoughts.*$", re.IGNORECASE),
    re.compile(r"^\s*please send (them|your thoughts) to .*@", re.IGNORECASE),
    re.compile(r"^\s*ian austen.*reports on canada.*$", re.IGNORECASE),
]

# Remove "Read:" lines commonly present in NYT newsletters etc.
RE_READ_COLON = re.compile(r"^\s*(read|from opinion)\s*:\s*", re.IGNORECASE)

# Remove bare image URL remnants / CDN paths in extracted text
RE_IMAGE_PATH_JUNK = re.compile(r"\b(static\d{2}\.|images\.)\S+\.(jpg|jpeg|png|webp)\b", re.IGNORECASE)
RE_HTML_FIGURE_BLOCK = re.compile(r"<figure\b[\s\S]*?</figure>", re.IGNORECASE)


def _requests_fetch(url: str, timeout: Tuple[int, int] = (10, 30)) -> str:
    """
    Fetch HTML with requests so we can control headers, retries, and get diagnostics.
    """
    headers = {
        # Browser-like UA helps with some sites
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fr-FR;q=0.7,fr;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    sess = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    sess.mount("https://", HTTPAdapter(max_retries=retries))
    sess.mount("http://", HTTPAdapter(max_retries=retries))

    r = sess.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    ct = r.headers.get("Content-Type", "")

    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} while fetching {url}")

    if "text/html" not in ct:
        # NYT sometimes serves HTML with atypical content-type, but usually this catches wrong content
        # Keep it soft: return anyway
        pass

    return r.text


def fetch_and_extract_from_url(url: str) -> str:
    """
    Try Trafilatura fetch first; if it fails, use requests fetch then extract.
    """
    html = trafilatura.fetch_url(url)

    if not html:
        # Fallback: requests with diagnostics
        try:
            html = _requests_fetch(url)
        except Exception as e:
            raise RuntimeError(f"Could not fetch URL via trafilatura or requests: {url} ({e})")

    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )

    if not extracted:
        # This happens on paywalls/JS-only pages. Give actionable hint.
        raise RuntimeError(
            "Fetched HTML but extraction failed. Possible paywall/consent/JS rendering required. "
            f"URL: {url}"
        )

    return extracted

def extract_from_html(html: str, url: Optional[str] = None) -> str:
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    if not extracted:
        raise RuntimeError("Trafilatura could not extract main content from provided HTML.")
    return extracted


def normalize_whitespace(text: str) -> str:
    # Normalize line endings and collapse excessive blank lines later
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Trim trailing spaces on each line
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def remove_line_if_boilerplate(line: str) -> bool:
    if RE_AD.match(line.strip()):
        return True
    for pat in BOILERPLATE_LINE_PATTERNS:
        if pat.match(line.strip()):
            return True
    # Drop empty "Read:"-style lines
    if RE_BRACKETED_READ.match(line.strip()):
        return True
    return False


def clean_text_rules(text: str, cut_after_heading: Optional[str] = None) -> str:
    text = normalize_whitespace(text)

    # If source is markdown-ish, reduce common constructs
    text = RE_HTML_FIGURE_BLOCK.sub(" ", text)
    text = RE_MD_IMAGE.sub(" ", text)
    text = RE_MD_LINK.sub(r"\1", text)

    # Remove URLs globally (BM25 poison)
    text = RE_URL.sub(" ", text)
    text = RE_IMAGE_PATH_JUNK.sub(" ", text)

    # Optional cutoff: remove everything after a specific heading marker
    if cut_after_heading:
        idx = text.find(cut_after_heading)
        if idx != -1:
            text = text[:idx].strip()

    # Line-by-line cleanup (remove boilerplate sections, "Read:" lines, etc.)
    cleaned_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()

        if not line:
            cleaned_lines.append("")
            continue

        # Remove “Read:” prefixes but keep any remaining meaningful text
        line = RE_READ_COLON.sub("", line).strip()

        # Drop obvious boilerplate
        if remove_line_if_boilerplate(line):
            continue

        # Drop lines that are just punctuation or very short noise
        if len(line) <= 2 and not RE_HEADING.match(line):
            continue

        cleaned_lines.append(line)

    # Collapse multiple blank lines
    out = []
    blank = False
    for line in cleaned_lines:
        if line == "":
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(line)
            blank = False

    return "\n".join(out).strip()


def read_input(path: Optional[str]) -> str:
    if not path:
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_output(path: Optional[str], text: str) -> None:
    if not path:
        print(text)
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Fetch + extract main content using trafilatura.")
    src.add_argument("--in", dest="in_path", help="Input file (html or text). If omitted, read stdin.")

    ap.add_argument("--html", action="store_true", help="Treat --in as raw HTML and run trafilatura.extract.")
    ap.add_argument("--source-url", default=None, help="Optional URL context for HTML extraction.")
    ap.add_argument("--cut-after-heading", default=None, help='Cut off everything after this exact heading text (e.g. "## Trans Canada").')
    ap.add_argument("--out", default=None, help="Write cleaned text to file (default: stdout).")
    args = ap.parse_args()

    # Stage 1: get plaintext
    if args.url:
        plain = fetch_and_extract_from_url(args.url)
    else:
        raw = read_input(args.in_path)
        if args.html:
            plain = extract_from_html(raw, url=args.source_url)
        else:
            plain = raw

    # Stage 2: apply deterministic cleanup rules
    cleaned = clean_text_rules(plain, cut_after_heading=args.cut_after_heading)

    write_output(args.out, cleaned)


if __name__ == "__main__":
    main()
