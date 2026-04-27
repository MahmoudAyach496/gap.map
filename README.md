# gap.map

A research gap discovery platform that turns scientific literature into a navigable knowledge graph.

## What It Does

gap.map accepts a free-text research prompt, fetches real academic papers, validates them, analyses them for knowledge gaps, and renders the result as an interactive visual map.

The app can:

- Extract useful semantic terms from a noisy research prompt.
- Fetch real papers from arXiv, OpenAlex, and Semantic Scholar.
- Validate paper data with Pydantic models.
- Scrape full text from ar5iv and open-access paper URLs via Unpaywall.
- Use OpenAI `gpt-4o-mini` to identify methodology, domain, replication, and action gaps.
- Render papers and gaps in 3D graph, 2D graph, and city views.
- Match selected papers or gaps to government grant data.

## Stack Used

### Backend

- Python
- FastAPI
- Pydantic
- httpx
- arxiv
- pyalex / OpenAlex
- Semantic Scholar Graph API
- OpenAI Python SDK
- python-dotenv

### Frontend

- Vanilla HTML
- CSS
- JavaScript
- Three.js for the 3D graph and city view
- Canvas for the 2D graph

### Data Sources

- arXiv
- OpenAlex
- Semantic Scholar
- Unpaywall
- ar5iv
- Seed grant data for UKRI, NASA, ESA, JAXA, JAMSTEC, NSF, DARPA, ERC, and Horizon Europe

## Workflow

1. The user enters a research focus, for example:

   ```text
   orbital debris vs ozone depletion
   ```

2. The backend extracts semantic terms from the prompt.

   Filler words are removed, important phrases are ranked, and clean source-specific queries are generated.

3. The backend fetches papers concurrently from:

   - arXiv
   - OpenAlex
   - Semantic Scholar

4. Every paper is validated through Pydantic.

   The canonical paper shape includes title, abstract, authors, year, domain, source, citation count, and URL.

5. The backend scrapes text for the first papers selected for analysis.

   It tries ar5iv for arXiv papers, Unpaywall for open-access DOI papers, and falls back to the abstract if scraping fails.

6. OpenAI analyses the scraped text.

   `gpt-4o-mini` identifies concrete methodology gaps, domain gaps, replication gaps, and suggested research actions.

7. Gap analysis results are converted into graph nodes.

   Each gap node is connected back to its source paper.

8. The frontend renders the result.

   Papers and gaps appear in the 3D graph, 2D graph, and city view. The gaps counter and gaps filter use the generated gap nodes.

## Run Locally

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

In a second terminal:

```bash
python3 -m http.server 5500
```

Open:

```text
http://localhost:5500/gap_map_unified.html
```

## Environment Variables

Create a `.env` file in the project root with:

```bash
OPENALEX_API_KEY=your_openalex_key
OPENALEX_EMAIL=your_email@example.com
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_key
OPENAI_API_KEY=your_openai_key
```

## Main API

### Health Check

```http
GET /
```

Returns:

```json
{"status": "ok"}
```

### Research Pipeline

```http
POST /research
```

Body:

```json
{
  "prompt": "orbital debris remediation and ozone depletion research gaps"
}
```

Returns papers, sources used, semantic query metadata, and generated gap nodes.

## Project Files

- `main.py` - FastAPI server and `/research` pipeline
- `models.py` - Pydantic models for papers, responses, semantic queries, and gaps
- `semantic_extractor.py` - cleans research prompts into source-specific queries
- `arxiv_fetcher.py` - arXiv paper fetching
- `openalex_fetcher.py` - OpenAlex paper fetching
- `semantic_scholar_fetcher.py` - Semantic Scholar paper fetching
- `scraper.py` - full-text scraping and abstract fallback
- `gap_analyser.py` - OpenAI-powered gap analysis
- `gap_node_builder.py` - converts gap analyses into graph nodes
- `gap_map_unified.html` - single-file frontend with onboarding, graph views, city view, sidebar, and grants

## Notes

- The first `/research` call can take around 30-60 seconds because it fetches papers, scrapes up to 10 papers, and runs OpenAI analysis sequentially.
- The frontend expects the backend to be running on `http://localhost:8000`.
- The frontend is served separately on `http://localhost:5500`.

## Author

Mahmoud Ayache  
[github.com/MahmoudAyach496](https://github.com/MahmoudAyach496)
