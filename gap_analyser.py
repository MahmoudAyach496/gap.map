import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from models import Paper, PaperGapAnalysis


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = 'You are a research gap analyst. Given a paper\'s text, identify concrete knowledge gaps. Return ONLY valid JSON matching this schema, no preamble: {"methodology_gaps":[],"domain_gaps":[],"replication_gaps":[],"suggested_actions":[]}. Each array max 2 items. Be specific and actionable.'

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def analyse_paper_gaps(paper: Paper) -> Optional[PaperGapAnalysis]:
    if client is None:
        return None

    text = (paper.scraped_text or paper.abstract or "")[:4000]
    if not text:
        return None

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return PaperGapAnalysis(
            paper_id=paper.id,
            paper_title=paper.title,
            methodology_gaps=payload.get("methodology_gaps") or [],
            domain_gaps=payload.get("domain_gaps") or [],
            replication_gaps=payload.get("replication_gaps") or [],
            suggested_actions=payload.get("suggested_actions") or [],
        )
    except Exception:
        return None
