"""Deterministic source-evidence retrieval over repository architecture artifacts."""

import re
from dataclasses import dataclass

from repolume_api.analysis_schemas import ArchitectureNodeResponse, RepositoryArchitectureResponse

_TOKEN = re.compile(r"[a-z0-9]+", re.ASCII)
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "does",
        "how",
        "implement",
        "implemented",
        "implementation",
        "in",
        "is",
        "it",
        "of",
        "the",
        "to",
        "what",
        "where",
        "which",
        "work",
        "works",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    """One ranked architecture node with repository-relative source evidence."""

    node: ArchitectureNodeResponse
    score: int
    matched_terms: tuple[str, ...]
    relationship_count: int


def _terms(value: str) -> tuple[str, ...]:
    expanded = _CAMEL_BOUNDARY.sub(" ", value)
    return tuple(
        "auth" if term.startswith("authenticat") else term
        for term in _TOKEN.findall(expanded.lower())
    )


def _question_terms(question: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(term for term in _terms(question) if term not in _STOP_WORDS))


def _field_terms(value: str | None) -> frozenset[str]:
    return frozenset(_terms(value or ""))


def _score_node(
    node: ArchitectureNodeResponse,
    terms: tuple[str, ...],
) -> tuple[int, tuple[str, ...]]:
    fields = (
        (6, _field_terms(node.name)),
        (5, _field_terms(node.qualified_name)),
        (5, _field_terms(node.location.path if node.location else None)),
        (3, _field_terms(node.detail)),
        (3, frozenset(term for decorator in node.decorators for term in _terms(decorator))),
        (1, _field_terms(node.language)),
        (1, _field_terms(node.kind)),
        (1, _field_terms(node.symbol_kind)),
    )
    matched: list[str] = []
    score = 0
    for term in terms:
        term_score = max((weight for weight, values in fields if term in values), default=0)
        if term_score:
            matched.append(term)
            score += term_score
    return score, tuple(matched)


def retrieve_evidence(
    architecture: RepositoryArchitectureResponse,
    question: str,
    *,
    limit: int = 5,
) -> tuple[EvidenceMatch, ...]:
    """Rank source-located nodes using transparent lexical evidence."""

    if not 1 <= limit <= 10:
        raise ValueError("limit must be between 1 and 10")
    terms = _question_terms(question)
    if not terms:
        return ()

    relationship_counts: dict[str, int] = {}
    for edge in architecture.edges:
        relationship_counts[edge.source] = relationship_counts.get(edge.source, 0) + 1
        relationship_counts[edge.target] = relationship_counts.get(edge.target, 0) + 1

    matches: list[EvidenceMatch] = []
    for node in architecture.nodes:
        if node.location is None or node.kind not in {"module", "symbol", "entry_point"}:
            continue
        score, matched_terms = _score_node(node, terms)
        if score == 0:
            continue
        matches.append(
            EvidenceMatch(
                node=node,
                score=score,
                matched_terms=matched_terms,
                relationship_count=relationship_counts.get(node.id, 0),
            )
        )

    matches.sort(
        key=lambda match: (
            -match.score,
            -len(match.matched_terms),
            match.node.location.path if match.node.location else "",
            match.node.location.line if match.node.location else 0,
            match.node.id,
        )
    )
    return tuple(matches[:limit])
