import asyncio
import logging
import re
from typing import List

import arxiv
from pydantic import ValidationError

from models import Domain, Paper


logger = logging.getLogger(__name__)

SPACE_QUERY = (
    '"space debris" OR "orbital debris" OR "space junk" OR '
    '"satellite collision avoidance" OR "orbital sustainability"'
)
OCEAN_QUERY = (
    '"deep ocean sustainability" OR "marine biodiversity deep sea" OR '
    '"deep sea pressure sensors" OR "hydrothermal vent research" OR '
    '"ocean acoustic navigation"'
)


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


def _fetch_papers(query: str, domain: Domain, themes: List[str], max_results: int) -> List[Paper]:
    client = arxiv.Client(
        page_size=max_results,
        delay_seconds=3.0,
        num_retries=3,
    )
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )

    papers: List[Paper] = []
    for result in client.results(search):
        try:
            paper_id = result.entry_id.rsplit("/", 1)[-1]
            papers.append(
                Paper(
                    id=f"arxiv:{paper_id}",
                    source="arxiv",
                    title=result.title,
                    abstract=result.summary,
                    authors=[author.name for author in result.authors],
                    year=result.published.year,
                    domain=domain,
                    themes=themes,
                    url=result.entry_id,
                    citation_count=0,
                )
            )
        except ValidationError as exc:
            logger.warning("Skipping invalid arXiv result: %s", exc)

    return papers


def fetch_space_papers(max_results: int = 20) -> List[Paper]:
    return _fetch_papers(
        query=SPACE_QUERY,
        domain=Domain.SPACE,
        themes=["space debris", "orbital debris", "satellite collision avoidance", "orbital sustainability"],
        max_results=max_results,
    )


def fetch_ocean_papers(max_results: int = 20) -> List[Paper]:
    return _fetch_papers(
        query=OCEAN_QUERY,
        domain=Domain.OCEAN,
        themes=["deep ocean", "marine biodiversity", "deep sea sensors", "hydrothermal vents", "acoustic navigation"],
        max_results=max_results,
    )


async def fetch_arxiv_query(query: str, max_results: int = 50) -> List[Paper]:
    sanitized_query = _sanitize_query(query)
    return await asyncio.to_thread(
        _fetch_papers,
        sanitized_query,
        Domain.BOTH,
        [sanitized_query],
        max_results,
    )
