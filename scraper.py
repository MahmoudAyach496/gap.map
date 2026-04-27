import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv

from models import Paper


load_dotenv()

OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL")


def _strip_html(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    paragraphs = re.findall(r"<p[^>]*>([\s\S]*?)</p>", html, flags=re.IGNORECASE)
    text = " ".join(paragraphs) if paragraphs else html
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return _strip_html(response.text)[:6000]


async def _unpaywall_oa_url(client: httpx.AsyncClient, doi: str) -> Optional[str]:
    if not OPENALEX_EMAIL:
        return None
    response = await client.get(
        "https://api.unpaywall.org/v2/%s" % doi,
        params={"email": OPENALEX_EMAIL},
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()
    best_location = payload.get("best_oa_location") or {}
    return best_location.get("url_for_html") or best_location.get("url")


async def scrape_paper(paper: Paper) -> Paper:
    fallback = paper.abstract or ""

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if paper.id.startswith("arxiv:"):
                arxiv_id = paper.id.replace("arxiv:", "", 1)
                text = await _fetch_text(client, "https://ar5iv.org/html/%s" % arxiv_id)
                if text:
                    paper.scraped_text = text
                    paper.used_fallback = False
                    return paper
        except Exception:
            pass

        try:
            doi = paper.doi
            if doi:
                oa_url = await _unpaywall_oa_url(client, doi)
                if oa_url:
                    text = await _fetch_text(client, oa_url)
                    if text:
                        paper.scraped_text = text
                        paper.used_fallback = False
                        return paper
        except Exception:
            pass

    paper.scraped_text = fallback
    paper.used_fallback = True
    return paper
