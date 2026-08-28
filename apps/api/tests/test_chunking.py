from __future__ import annotations

import pytest

from app.catalog.chunking import chunk_text


def test_empty_text_produces_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_is_a_single_chunk() -> None:
    text = "Hold time is the duration a task sits with its assignee."
    chunks = chunk_text(text, max_chars=800)

    assert chunks == [text]


def test_short_paragraphs_are_packed_together() -> None:
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    chunks = chunk_text(text, max_chars=800)

    assert len(chunks) == 1
    assert "Paragraph one." in chunks[0]
    assert "Paragraph three." in chunks[0]


def test_paragraphs_split_into_separate_chunks_once_max_chars_exceeded() -> None:
    paragraph_a = "A" * 500
    paragraph_b = "B" * 500
    chunks = chunk_text(f"{paragraph_a}\n\n{paragraph_b}", max_chars=800)

    assert len(chunks) == 2
    assert chunks[0] == paragraph_a
    assert chunks[1] == paragraph_b


def test_long_paragraph_falls_back_to_sliding_window_with_overlap() -> None:
    # Position-identifiable text (not a repeated character) so exact window
    # boundaries and overlap can be checked precisely.
    long_text = "".join(f"{i:04d}" for i in range(500))  # 2000 chars
    chunks = chunk_text(long_text, max_chars=800, overlap=100)

    assert len(chunks) == 3
    assert chunks[0] == long_text[0:800]
    assert chunks[1] == long_text[700:1500]
    assert chunks[2] == long_text[1400:2000]
    assert chunks[0][-100:] == chunks[1][:100]
    assert chunks[1][-100:] == chunks[2][:100]


def test_chunking_is_deterministic() -> None:
    text = "One.\n\n" + ("Two. " * 50) + "\n\nThree."
    assert chunk_text(text) == chunk_text(text)


def test_invalid_max_chars_or_overlap_raise() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=0)
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("hello", max_chars=100, overlap=-1)
