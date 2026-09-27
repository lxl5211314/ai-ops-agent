import re

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    heading = ""
    buf: list[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            if buf:
                parts.append((heading, "\n".join(buf).strip()))
                buf = []
            heading = line.lstrip("#").strip()
        else:
            buf.append(line)
    if buf:
        parts.append((heading, "\n".join(buf).strip()))
    return [(h, b) for h, b in parts if b]


def _window(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for start in range(0, len(text), step):
        piece = text[start : start + CHUNK_SIZE]
        if not piece:
            break
        chunks.append(piece)
        if start + CHUNK_SIZE >= len(text):
            break
    return chunks


def chunk_text(text: str) -> list[tuple[str, str]]:
    """Return list of (heading, chunk)."""
    out: list[tuple[str, str]] = []
    for heading, block in _split_by_headings(text):
        for piece in _window(block):
            out.append((heading, piece))
    return out or ([("", text[:CHUNK_SIZE])] if text.strip() else [])


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_\-.]{2,}", text)
    han = re.findall(r"[一-鿿]{2,}", text)
    grams: list[str] = []
    for seg in han:
        grams.extend(seg[i : i + 2] for i in range(max(1, len(seg) - 1)))
    seen, out = set(), []
    for kw in words + grams:
        k = kw.lower()
        if k not in seen:
            seen.add(k)
            out.append(kw)
        if len(out) >= limit:
            break
    return out
