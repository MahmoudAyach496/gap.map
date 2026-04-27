import asyncio
import logging
from typing import Callable, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from arxiv_fetcher import fetch_arxiv_query
from arxiv_fetcher import fetch_ocean_papers as fetch_arxiv_ocean_papers
from arxiv_fetcher import fetch_space_papers as fetch_arxiv_space_papers
from gap_analyser import analyse_paper_gaps
from gap_node_builder import build_gap_nodes
from models import Domain, GraphResponse, Paper, SearchQuery
from openalex_fetcher import fetch_openalex_query
from openalex_fetcher import fetch_ocean_papers as fetch_openalex_ocean_papers
from openalex_fetcher import fetch_space_papers as fetch_openalex_space_papers
from scraper import scrape_paper
from semantic_extractor import SemanticQuery, extract_semantic_query
from semantic_scholar_fetcher import fetch_semantic_scholar_query


logger = logging.getLogger(__name__)
MAX_PAPERS_TO_ANALYSE = 10


class ResearchPrompt(BaseModel):
    prompt: str = Field(..., min_length=10)


app = FastAPI(title="gap.map API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_fetch(fetcher: Callable[[int], List[Paper]], max_results: int) -> List[Paper]:
    try:
        return fetcher(max_results)
    except Exception as exc:
        logger.warning("Paper fetch failed: %s", exc)
        return []


def _graph_response(papers: List[Paper], sources_used: List[str]) -> GraphResponse:
    return GraphResponse(
        papers=papers,
        total=len(papers),
        sources_used=sources_used,
    )


def _filter_by_year(papers: List[Paper], year_from: Optional[int]) -> List[Paper]:
    if year_from is None:
        return papers
    return [paper for paper in papers if paper.year >= year_from]


def _filter_by_query(papers: List[Paper], query: str) -> List[Paper]:
    query_text = query.lower()
    filtered: List[Paper] = []

    for paper in papers:
        haystack = " ".join(
            [
                paper.title,
                paper.abstract or "",
                " ".join(paper.themes),
                " ".join(paper.authors),
            ]
        ).lower()
        if query_text in haystack:
            filtered.append(paper)

    return filtered


@app.get("/")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/papers/space")
def get_space_papers(max_results: int = 20) -> GraphResponse:
    papers = [
        *_safe_fetch(fetch_arxiv_space_papers, max_results),
        *_safe_fetch(fetch_openalex_space_papers, max_results),
    ]
    return _graph_response(papers, sources_used=["arxiv", "openalex"])


@app.get("/papers/ocean")
def get_ocean_papers(max_results: int = 20) -> GraphResponse:
    papers = [
        *_safe_fetch(fetch_arxiv_ocean_papers, max_results),
        *_safe_fetch(fetch_openalex_ocean_papers, max_results),
    ]
    return _graph_response(papers, sources_used=["arxiv", "openalex"])


@app.post("/search")
def search_papers(search_query: SearchQuery) -> GraphResponse:
    papers: List[Paper] = []

    if search_query.domain in (Domain.SPACE, Domain.BOTH):
        papers.extend(_safe_fetch(fetch_arxiv_space_papers, search_query.max_results))
        papers.extend(_safe_fetch(fetch_openalex_space_papers, search_query.max_results))

    if search_query.domain in (Domain.OCEAN, Domain.BOTH):
        papers.extend(_safe_fetch(fetch_arxiv_ocean_papers, search_query.max_results))
        papers.extend(_safe_fetch(fetch_openalex_ocean_papers, search_query.max_results))

    papers = _filter_by_year(papers, search_query.year_from)
    papers = _filter_by_query(papers, search_query.query)

    return _graph_response(papers, sources_used=["arxiv", "openalex"])


@app.post("/research")
async def research_papers(research_prompt: ResearchPrompt) -> GraphResponse:
    sq = extract_semantic_query(research_prompt.prompt)
    source_fetches = [
        ("arxiv", fetch_arxiv_query(sq.arxiv_query, 50)),
        ("openalex", fetch_openalex_query(sq.openalex_query, 50)),
        ("semanticscholar", fetch_semantic_scholar_query(sq.semanticscholar_query, 50)),
    ]
    results = await asyncio.gather(
        *[fetch for _, fetch in source_fetches],
        return_exceptions=True,
    )

    combined: List[Paper] = []
    sources_used: List[str] = []

    for index, result in enumerate(results):
        source = source_fetches[index][0]
        if isinstance(result, Exception):
            logger.warning("%s research fetch failed: %s", source, result)
            continue
        if not result:
            logger.warning("%s research fetch returned no papers", source)
            continue

        combined.extend(result)
        sources_used.append(source)

    papers_to_analyse = combined[:MAX_PAPERS_TO_ANALYSE]
    scraped_results = await asyncio.gather(
        *[scrape_paper(paper) for paper in papers_to_analyse],
        return_exceptions=True,
    )
    scraped_papers: List[Paper] = []
    for result in scraped_results:
        if isinstance(result, Exception):
            continue
        scraped_papers.append(result)

    analyses = []
    for paper in scraped_papers:
        analysis = await analyse_paper_gaps(paper)
        if analysis is not None:
            analyses.append(analysis)
        await asyncio.sleep(0.3)

    gap_nodes = build_gap_nodes(analyses, combined)
    logger.info("Analysed %s papers, generated %s gap nodes", len(analyses), len(gap_nodes))

    return GraphResponse(
        papers=combined,
        total=len(combined),
        sources_used=sources_used,
        semantic_query=sq,
        gap_nodes=gap_nodes,
    )
