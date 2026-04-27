import re
from collections import Counter
from typing import Dict, List

from pydantic import BaseModel


STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "i",
    "we",
    "my",
    "our",
    "looking",
    "want",
    "trying",
    "find",
    "help",
    "about",
    "some",
    "any",
    "thing",
    "things",
    "please",
    "can",
    "could",
    "would",
    "like",
    "just",
    "really",
    "very",
    "also",
    "and",
    "but",
    "or",
    "so",
    "if",
    "then",
    "that",
    "this",
    "with",
    "for",
    "from",
    "into",
    "onto",
    "it",
    "its",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "be",
    "been",
    "being",
    "show",
    "tell",
    "give",
    "get",
    "make",
    "need",
    "use",
    "see",
    "know",
    "what",
    "when",
    "where",
    "why",
    "how",
    "on",
    "in",
    "at",
    "to",
    "of",
    "by",
}


class SemanticQuery(BaseModel):
    raw_input: str
    terms: List[str]
    arxiv_query: str
    openalex_query: str
    semanticscholar_query: str


def _clean_input(raw: str) -> str:
    cleaned = re.sub(r'[,.?!:;()\[\]{}\"\']', ' ', raw.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _cap_arxiv_query(terms: List[str], max_chars: int = 200) -> str:
    parts: List[str] = []
    for term in terms:
        part = '"%s"' % term if " " in term else term
        candidate = " OR ".join(parts + [part])
        if len(candidate) > max_chars:
            break
        parts.append(part)
    return " OR ".join(parts)


def extract_semantic_query(raw: str) -> SemanticQuery:
    cleaned = _clean_input(raw)
    tokens = cleaned.split()
    filtered = [token for token in tokens if token not in STOPWORDS and len(token) >= 3]
    frequencies: Dict[str, int] = dict(Counter(filtered))

    phrase_candidates: List[str] = []
    for size in (3, 2):
        for index in range(0, len(tokens) - size + 1):
            window = tokens[index : index + size]
            if all(token not in STOPWORDS and len(token) >= 3 for token in window):
                phrase_candidates.append(" ".join(window))

    candidates = _dedupe_preserve_order(phrase_candidates + filtered)
    first_seen = {term: index for index, term in enumerate(candidates)}

    def specificity_key(term: str):
        is_phrase = " " in term
        term_frequency = min(frequencies.get(part, 1) for part in term.split())
        return (
            0 if is_phrase else 1,
            -len(term),
            term_frequency,
            first_seen[term],
        )

    terms = sorted(candidates, key=specificity_key)[:8]
    open_query = " ".join(terms[:3])

    return SemanticQuery(
        raw_input=raw,
        terms=terms,
        arxiv_query=_cap_arxiv_query(terms[:5]),
        openalex_query=open_query,
        semanticscholar_query=open_query,
    )
