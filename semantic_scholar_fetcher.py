import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from models import Domain, Paper


load_dotenv()

SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = "paperId,title,abstract,authors,year,citationCount,externalIds,url"

logger = logging.getLogger(__name__)


def _author_names(record: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for author in record.get("authors") or []:
        name = author.get("name")
        if name:
            names.append(name)
    return names


def _sanitize_query(query: str, max_chars: int = 100) -> str:
    """Strip punctuation that confuses search APIs and shorten to keywords."""
    # Remove punctuation that breaks filter syntax: , . ? ! : ; ( ) [ ] { } " '
    cleaned = re.sub(r'[,.?!:;()\[\]{}\"\']', ' ', query)
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Truncate to keyword-like length
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(' ', 1)[0]
    return cleaned


def _semantic_paper(record: Dict[str, Any]) -> Optional[Paper]:
    paper_id = record.get("paperId")
    if not paper_id:
        return None

    try:
        return Paper(
            id="semanticscholar:%s" % paper_id,
            source="semanticscholar",
            title=record.get("title") or "",
            abstract=record.get("abstract"),
            authors=_author_names(record),
            year=record.get("year"),
            domain=Domain.BOTH,
            themes=[],
            url=record.get("url"),
            citation_count=record.get("citationCount") or 0,
        )
    except ValidationError as exc:
        logger.warning(
            "Skipping invalid Semantic Scholar record id=%s title=%s errors=%s",
            paper_id,
            record.get("title"),
            exc.errors(),
        )
        return None


async def fetch_semantic_scholar_query(query: str, max_results: int = 50) -> List[Paper]:
    papers: List[Paper] = []
    sanitized_query = _sanitize_query(query)
    offset = 0
    retried_rate_limit = False
    headers: Dict[str, str] = {}

    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    logger.info(
        "Semantic Scholar query fetch start: api_key_prefix=%s has_api_key_header=%s query=%s sanitized_query=%s fields=%s",
        SEMANTIC_SCHOLAR_API_KEY[:4] if SEMANTIC_SCHOLAR_API_KEY else "",
        "x-api-key" in headers,
        query,
        sanitized_query,
        SEMANTIC_SCHOLAR_FIELDS,
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(papers) < max_results:
            remaining = max_results - len(papers)
            params: Dict[str, Any] = {
                "query": sanitized_query,
                "fields": SEMANTIC_SCHOLAR_FIELDS,
                "limit": min(remaining, 100),
                "offset": offset,
            }

            try:
                request = client.build_request("GET", SEMANTIC_SCHOLAR_SEARCH_URL, params=params, headers=headers)
                logger.info("Semantic Scholar exact request URL: %s", request.url)
                response = await client.send(request)
            except httpx.HTTPError as exc:
                logger.warning("Semantic Scholar request failed: %s", exc)
                logger.info("Semantic Scholar final mapped count: 0")
                return []

            logger.info("Semantic Scholar HTTP status code: %s", response.status_code)
            if response.status_code != 200:
                logger.warning("Semantic Scholar non-200 response body: %s", response.text[:500])

            if response.status_code == 429:
                if retried_rate_limit:
                    logger.warning("Semantic Scholar rate limit persisted after retry")
                    logger.info("Semantic Scholar final mapped count: %s", len(papers))
                    return papers
                retried_rate_limit = True
                await asyncio.sleep(5)
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.warning("Semantic Scholar HTTP error: %s", exc)
                logger.info("Semantic Scholar final mapped count: 0")
                return []

            payload = response.json()
            records = payload.get("data") or []
            logger.info("Semantic Scholar response.json()['data'] count before Pydantic mapping: %s", len(records))

            for record in records:
                paper = _semantic_paper(record)
                if paper is not None:
                    papers.append(paper)
                    if len(papers) >= max_results:
                        break

            next_offset = payload.get("next")
            if next_offset is None:
                break
            offset = next_offset

    logger.info("Semantic Scholar final mapped count: %s", len(papers))
    return papers
