"""Deterministic document chunking (FR-002).

Splits catalog document content into embeddable pieces. Prefers paragraph
boundaries, packing consecutive short paragraphs into one chunk up to
max_chars; a single paragraph longer than max_chars falls back to a fixed
sliding window with overlap so no chunk ever silently exceeds the limit.
Pure function, no I/O -- same input always produces the same chunks.
"""

from __future__ import annotations

DEFAULT_MAX_CHARS = 800
DEFAULT_OVERLAP = 100


def chunk_text(
    text: str, *, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be >= 0 and < max_chars")

    normalized = text.strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()] or [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            chunks.extend(_sliding_window(paragraph, max_chars, overlap))

    if current:
        chunks.append(current)

    return chunks


def _sliding_window(text: str, max_chars: int, overlap: int) -> list[str]:
    step = max_chars - overlap
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        windows.append(text[start:end])
        if end >= len(text):
            break
        start += step
    return windows
