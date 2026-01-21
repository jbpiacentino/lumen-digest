from langdetect import DetectorFactory, LangDetectException, detect

from .classifier import clean_text

DetectorFactory.seed = 0


def detect_language(text: str, default: str = "en") -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return default
    try:
        return detect(cleaned)
    except LangDetectException:
        return default
