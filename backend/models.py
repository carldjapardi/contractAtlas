"""Validated HTTP boundary; retrieval modules use plain dictionaries internally."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    mode: Literal["baseline", "cognee"] = "baseline"

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter a question with at least three characters.")
        return value


class GraphNode(BaseModel):
    id: str
    type: Literal["agency", "award", "recipient", "parent", "topic"]
    label: str
    sublabel: str = ""
    award_ids: list[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str
    origin: Literal["reported", "inferred"]
    award_ids: list[str] = Field(default_factory=list)


class Graph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = False


class Evidence(BaseModel):
    id: str
    title: str
    description: str
    source_url: str
    obligation: float
    agency: str
    recipient_name: str


class Answer(BaseModel):
    answer: str
    evidence: list[Evidence]
    graph: Graph
    mode: Literal["baseline", "cognee"]
    elapsed_ms: float
    coverage_notes: list[str]
    matched_count: int


class ResearchRequest(BaseModel):
    question: str = Field(min_length=10, max_length=4000)
    profile: str = Field(min_length=10, max_length=4000)

    @field_validator("question", "profile")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Provide at least ten characters of useful context.")
        return value


class ImproveRequest(BaseModel):
    feedback: str = Field(min_length=10, max_length=4000)

    @field_validator("feedback")
    @classmethod
    def meaningful_feedback(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Describe a useful correction or lasting team preference.")
        return value
