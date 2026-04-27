import re
from typing import Dict, List

from models import GapNode, Paper, PaperGapAnalysis


def _gap_id(paper_id: str, gap_type: str, index: int) -> str:
    safe_paper_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", paper_id)
    return "gap_%s_%s_%s" % (safe_paper_id, gap_type, index)


def build_gap_nodes(analyses: List[PaperGapAnalysis], papers: List[Paper]) -> List[GapNode]:
    papers_by_id: Dict[str, Paper] = {paper.id: paper for paper in papers}
    nodes: List[GapNode] = []

    for analysis in analyses:
        source = papers_by_id.get(analysis.paper_id)
        domain = source.domain.value if source else "both"
        year = source.year if source else 2026
        groups = [
            ("methodology", analysis.methodology_gaps),
            ("domain", analysis.domain_gaps),
            ("replication", analysis.replication_gaps),
            ("action", analysis.suggested_actions),
        ]

        for gap_type, items in groups:
            for index, description in enumerate(items):
                nodes.append(
                    GapNode(
                        id=_gap_id(analysis.paper_id, gap_type, index),
                        source_paper_id=analysis.paper_id,
                        source_paper_title=analysis.paper_title,
                        gap_type=gap_type,
                        description=description,
                        domain=domain,
                        year=year,
                    )
                )

    return nodes
