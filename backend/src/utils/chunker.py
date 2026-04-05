"""
Document chunking for RAG pipelines (BE-FILE-03).
Splits text into overlapping chunks of configurable size.
"""
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    text: str
    start_char: int
    end_char: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    doc_id: str = "",
) -> list[Chunk]:
    """
    Split text into overlapping chunks.
    Attempts to split on paragraph/sentence boundaries before hard-cutting.
    """
    if not text:
        return []

    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk_text_str = text[start:]
        else:
            # Try to break on a paragraph boundary
            break_pos = text.rfind("\n\n", start, end)
            if break_pos == -1 or break_pos <= start:
                # Try sentence boundary
                break_pos = text.rfind(". ", start, end)
            if break_pos == -1 or break_pos <= start:
                break_pos = end
            else:
                break_pos += 1  # include the period / blank line

            chunk_text_str = text[start:break_pos]
            end = break_pos

        chunks.append(Chunk(
            index=idx,
            text=chunk_text_str.strip(),
            start_char=start,
            end_char=end,
            metadata={"doc_id": doc_id, "chunk_index": idx},
        ))

        idx += 1
        start = end - overlap if end - overlap > start else end

    return chunks


def chunks_to_dicts(chunks: list[Chunk]) -> list[dict]:
    return [
        {
            "index": c.index,
            "text": c.text,
            "start_char": c.start_char,
            "end_char": c.end_char,
            "metadata": c.metadata,
        }
        for c in chunks
    ]
