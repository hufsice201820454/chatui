from __future__ import annotations

from typing import Dict, List, Sequence
import math
import re
from collections import Counter, defaultdict


_WORD_RE = re.compile(r"\w+")


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


class Bm25Index:
    """
    외부 라이브러리 없이 구현한 간단한 BM25 인덱스.
    - documents: {"id", "text", "meta"} 형태 리스트
    - search(query, top_k) -> 스코어가 포함된 문서 리스트
    """

    def __init__(self, documents: Sequence[Dict]):
        self._docs: List[Dict] = list(documents)
        self._doc_tokens: List[List[str]] = []
        self._df: Dict[str, int] = defaultdict(int)
        self._avgdl: float = 0.0

        self._build()

    def _build(self) -> None:
        total_len = 0
        for doc in self._docs:
            tokens = _tokenize(doc.get("text") or "")
            self._doc_tokens.append(tokens)
            total_len += len(tokens)
            for term in set(tokens):
                self._df[term] += 1
        self._avgdl = (total_len / len(self._docs)) if self._docs else 0.0

    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        if not self._docs:
            return []

        q_terms = _tokenize(query)
        if not q_terms:
            return []

        scores: List[tuple[int, float]] = []
        for idx, tokens in enumerate(self._doc_tokens):
            score = self._score_document(tokens, q_terms)
            if score > 0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        result: List[Dict] = []
        for idx, score in scores[:top_k]:
            doc = dict(self._docs[idx])  # shallow copy
            doc["score"] = score
            result.append(doc)
        return result

    def _score_document(self, tokens: List[str], q_terms: List[str]) -> float:
        # BM25 기본 파라미터
        k1 = 1.5
        b = 0.75
        if not tokens:
            return 0.0

        doc_len = len(tokens)
        freqs = Counter(tokens)
        score = 0.0
        N = len(self._docs)

        for term in q_terms:
            df = self._df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (N - df + 0.5) / (df + 0.5))
            f = freqs.get(term, 0)
            if f == 0:
                continue
            denom = f + k1 * (1 - b + b * doc_len / (self._avgdl or 1.0))
            score += idf * (f * (k1 + 1) / denom)
        return score

