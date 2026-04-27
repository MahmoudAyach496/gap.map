from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

from semantic_extractor import SemanticQuery


class Domain(str, Enum):
    SPACE = "space"
    OCEAN = "ocean"
    BOTH = "both"


class NodeType(str, Enum):
    PAPER = "paper"
    LAB = "lab"
    GAP = "gap"
    BRIDGE = "bridge"
    USER = "user"


class Paper(BaseModel):
    id: str = Field(..., description="arxiv:xxx or openalex:Wxxx")
    source: str
    title: str = Field(..., min_length=3, max_length=500)
    abstract: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: int = Field(..., ge=1900, le=2030)
    domain: Domain
    themes: List[str] = Field(default_factory=list)
    url: Optional[HttpUrl] = None
    doi: Optional[str] = None
    citation_count: int = Field(default=0, ge=0)
    node_type: NodeType = NodeType.PAPER
    scraped_text: Optional[str] = None
    used_fallback: bool = False


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=2)
    domain: Domain
    max_results: int = Field(default=20, ge=1, le=100)
    year_from: Optional[int] = Field(default=None, ge=1900)


class PaperGapAnalysis(BaseModel):
    paper_id: str
    paper_title: str
    methodology_gaps: List[str] = Field(default_factory=list)
    domain_gaps: List[str] = Field(default_factory=list)
    replication_gaps: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)


class GapNode(BaseModel):
    id: str
    source_paper_id: str
    source_paper_title: str
    gap_type: str
    description: str
    domain: str
    year: int


class GraphResponse(BaseModel):
    papers: List[Paper]
    total: int
    sources_used: List[str]
    semantic_query: Optional[SemanticQuery] = None
    gap_nodes: List[GapNode] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.now)
