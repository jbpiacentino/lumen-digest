import re
from typing import Optional


# -----------------------------
# Regex patterns: remove noise that distorts lexical matching
# -----------------------------
RE_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")                 # ![alt](url)
RE_URL = re.compile(r"https?://\S+")
RE_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")                # [text](url) -> text
RE_BRACKETED_READ = re.compile(r"^\s*\[\*?(read|from opinion)\b.*$", re.IGNORECASE)
RE_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
RE_AD = re.compile(r"^\s*(advertisement|skip advertisement)\s*$", re.IGNORECASE)
RE_HTML_FIGURE_BLOCK = re.compile(r"<figure\b[\s\S]*?</figure>", re.IGNORECASE)

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


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def remove_line_if_boilerplate(line: str) -> bool:
    if RE_AD.match(line.strip()):
        return True
    for pat in BOILERPLATE_LINE_PATTERNS:
        if pat.match(line.strip()):
            return True
    if RE_BRACKETED_READ.match(line.strip()):
        return True
    return False


def clean_text_rules(text: str, cut_after_heading: Optional[str] = None) -> str:
    text = normalize_whitespace(text)

    text = RE_HTML_FIGURE_BLOCK.sub(" ", text)

    text = RE_MD_IMAGE.sub(" ", text)
    text = RE_MD_LINK.sub(r"\1", text)

    text = RE_URL.sub(" ", text)
    text = RE_IMAGE_PATH_JUNK.sub(" ", text)

    if cut_after_heading:
        idx = text.find(cut_after_heading)
        if idx != -1:
            text = text[:idx].strip()

    cleaned_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if remove_line_if_boilerplate(line):
            continue
        if RE_HEADING.match(line):
            cleaned_lines.append(line)
            continue
        line = RE_READ_COLON.sub("", line).strip()
        if line:
            cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = normalize_whitespace(cleaned)
    return cleaned
