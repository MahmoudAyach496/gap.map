import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

import httpx
import pyalex
from dotenv import load_dotenv
from pyalex import Works
from pydantic import ValidationError

from models import Domain, Paper


load_dotenv()

OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL")
OPENALEX_WORKS_URL = "https://api.openalex.org/works"

if OPENALEX_EMAIL:
    pyalex.config.email = OPENALEX_EMAIL
if OPENALEX_API_KEY:
    pyalex.config.api_key = OPENALEX_API_KEY

logger = logging.getLogger(__name__)

SPACE_FILTERS = [
    "space debris",
    "orbital debris",
    "space junk",
    "satellite collision avoidance",
    "orbital sustainability",
]
OCEAN_FILTERS = [
    "deep ocean sustainability",
    "marine biodiversity deep sea",
    "deep sea pressure sensors",
    "hydrothermal vent research",
    "ocean acoustic navigation",
]


def _openalex_id(raw_id: Optional[str]) -> str:
    if not raw_id:
        return ""
    return raw_id.rsplit("/", 1)[-1]


def _authorship_names(work: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(name)
    return names


def _clean_title(title: Optional[str]) -> str:
    if not title:
        return ""
    return re.sub(r"<[^>]+>", "", title).strip()


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


def _openalex_key_prefix() -> str:
    if not OPENALEX_API_KEY:
        return ""
    return OPENALEX_API_KEY[:4]


def _openalex_query_url(query: str, max_results: int, include_real_key: bool) -> str:
    api_key = None
    if OPENALEX_API_KEY:
        api_key = OPENALEX_API_KEY if include_real_key else "%s..." % _openalex_key_prefix()
    params: Dict[str, Any] = {
        "search": query,
        "per-page": min(max_results, 50),
    }
    if api_key:
        params["api_key"] = api_key
    return str(httpx.URL(OPENALEX_WORKS_URL, params=params))


def _fetch_papers(filters: List[str], domain: Domain, max_results: int) -> List[Paper]:
    papers: List[Paper] = []
    seen_ids: Set[str] = set()

    for phrase in filters:
        remaining = max_results - len(papers)
        if remaining <= 0:
            break

        works = (
            Works()
            .filter(**{"title_and_abstract.search": phrase})
            .sort(publication_year="desc")
            .get(per_page=remaining)
        )

        for work in works:
            work_id = _openalex_id(work.get("id"))
            if not work_id or work_id in seen_ids:
                continue

            try:
                paper = Paper(
                    id=f"openalex:{work_id}",
                    source="openalex",
                    title=work.get("display_name") or work.get("title") or "",
                    abstract=work.get("abstract"),
                    authors=_authorship_names(work),
                    year=work.get("publication_year"),
                    domain=domain,
                    themes=[phrase],
                    url=work.get("id"),
                    citation_count=work.get("cited_by_count") or 0,
                )
            except ValidationError as exc:
                logger.warning("Skipping invalid OpenAlex record: %s", exc)
                continue

            seen_ids.add(work_id)
            papers.append(paper)

    return papers


def fetch_space_papers(max_results: int = 20) -> List[Paper]:
    return _fetch_papers(
        filters=SPACE_FILTERS,
        domain=Domain.SPACE,
        max_results=max_results,
    )


def fetch_ocean_papers(max_results: int = 20) -> List[Paper]:
    return _fetch_papers(
        filters=OCEAN_FILTERS,
        domain=Domain.OCEAN,
        max_results=max_results,
    )


def _fetch_openalex_query_sync(query: str, max_results: int) -> List[Paper]:
    papers: List[Paper] = []
    sanitized_query = _sanitize_query(query)
    logger.info(
        "OpenAlex query fetch start: api_key_prefix=%s email=%s query=%s sanitized_query=%s",
        _openalex_key_prefix(),
        OPENALEX_EMAIL,
        query,
        sanitized_query,
    )
    logger.info("OpenAlex request URL: %s", _openalex_query_url(sanitized_query, max_results, include_real_key=False))

    try:
        response = httpx.get(_openalex_query_url(sanitized_query, max_results, include_real_key=True), timeout=30.0)
        logger.info("OpenAlex raw response status: %s", response.status_code)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("OpenAlex HTTP error: %s", exc)
        logger.info("OpenAlex final mapped count: 0")
        return []

    payload = response.json()
    works = payload.get("results") or []
    logger.info("OpenAlex raw result count before Pydantic mapping: %s", len(works))

    for work in works:
        work_id = _openalex_id(work.get("id"))
        if not work_id:
            continue

        title = _clean_title(work.get("display_name") or work.get("title"))
        if not title:
            logger.debug("Skipping OpenAlex record with empty title id=%s", work_id)
            continue

        try:
            papers.append(
                Paper(
                    id=f"openalex:{work_id}",
                    source="openalex",
                    title=title,
                    abstract=work.get("abstract"),
                    authors=_authorship_names(work),
                    year=work.get("publication_year"),
                    domain=Domain.BOTH,
                    themes=[sanitized_query],
                    url=work.get("id"),
                    citation_count=work.get("cited_by_count") or 0,
                )
            )
        except ValidationError as exc:
            logger.warning(
                "Skipping invalid OpenAlex record id=%s title=%s errors=%s",
                work_id,
                title,
                exc.errors(),
            )
            continue

    logger.info("OpenAlex final mapped count: %s", len(papers))
    return papers


async def fetch_openalex_query(query: str, max_results: int = 50) -> List[Paper]:
    return await asyncio.to_thread(_fetch_openalex_query_sync, query, max_results)
