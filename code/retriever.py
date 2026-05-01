"""
SupportBrain — retriever.py
Corpus loader and TF-IDF based search engine.
"""

import os
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHUNK_SIZE_WORDS = 300
TOP_K_DEFAULT = 3

COMPANY_DIRS: dict[str, str] = {
    "HackerRank": "data/hackerrank",
    "Claude": "data/claude",
    "Visa": "data/visa",
}


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS) -> list[str]:
    """Split text into overlapping word chunks."""
    words = text.split()
    chunks = []
    step = chunk_size // 2  # 50% overlap
    for i in range(0, max(len(words), 1), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def _load_corpus(company: str, repo_root: str) -> list[str]:
    """Load all text files for a company and return a list of text chunks."""
    rel_dir = COMPANY_DIRS.get(company)
    if not rel_dir:
        return []
    corpus_dir = Path(repo_root) / rel_dir
    if not corpus_dir.exists():
        return []

    all_chunks: list[str] = []
    for filepath in sorted(corpus_dir.glob("*.txt")):
        try:
            text = filepath.read_text(encoding="utf-8")
            all_chunks.extend(_chunk_text(text))
        except Exception:
            pass
    return all_chunks


class Retriever:
    """
    TF-IDF based retrieval engine. Maintains a per-company index.
    """

    def __init__(self, repo_root: str) -> None:
        self._repo_root = repo_root
        # company → (chunks_list, TfidfVectorizer, tfidf_matrix)
        self._indexes: dict[str, tuple] = {}

    def load_all(self) -> dict[str, int]:
        """Load corpus for all companies. Returns {company: chunk_count}."""
        counts: dict[str, int] = {}
        for company in COMPANY_DIRS:
            chunks = _load_corpus(company, self._repo_root)
            counts[company] = len(chunks)
            if chunks:
                vectorizer = TfidfVectorizer(
                    stop_words="english",
                    ngram_range=(1, 2),
                    max_features=5000,
                )
                matrix = vectorizer.fit_transform(chunks)
                self._indexes[company] = (chunks, vectorizer, matrix)
        return counts

    def search(
        self,
        query: str,
        company: str,
        top_k: int = TOP_K_DEFAULT,
    ) -> list[str]:
        """
        Retrieve the top_k most relevant chunks for a query from the company corpus.
        Returns a list of text strings (empty list if no corpus).
        """
        if company not in self._indexes:
            return []
        chunks, vectorizer, matrix = self._indexes[company]
        try:
            q_vec = vectorizer.transform([query])
            sims = cosine_similarity(q_vec, matrix)[0]
            top_indices = sims.argsort()[::-1][:top_k]
            return [chunks[i] for i in top_indices if sims[i] > 0]
        except Exception:
            return []
