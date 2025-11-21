import re


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    return text


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = text[:8192]
    return text

