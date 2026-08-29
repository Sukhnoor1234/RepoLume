"""Unit tests for conservative, source-grounded repository answers."""

import pytest

from repolume_api.analysis_schemas import ArchitectureNodeResponse
from repolume_api.evidence_retrieval import EvidenceMatch
from repolume_api.repository_answers import compose_grounded_answer


def _match(
    node_id: str,
    name: str,
    path: str,
    line: int,
    end_line: int,
) -> EvidenceMatch:
    return EvidenceMatch(
        node=ArchitectureNodeResponse.model_validate(
            {
                "id": node_id,
                "kind": "symbol",
                "name": name,
                "language": "python",
                "location": {"path": path, "line": line, "end_line": end_line},
                "symbol_kind": "function",
                "confidence": "confirmed",
            }
        ),
        score=10,
        matched_terms=("order",),
        relationship_count=2,
    )


def test_composes_numbered_answer_from_bounded_evidence() -> None:
    matches = (
        _match("symbol:create", "create_order", "orders/service.py", 12, 25),
        _match("symbol:save", "save_order", "orders/storage.py", 8, 8),
        _match("symbol:route", "post_order", "orders/routes.py", 20, 31),
        _match("symbol:extra", "order_helper", "orders/helpers.py", 1, 4),
    )

    answer = compose_grounded_answer("How is an order created?", matches)

    assert answer.grounding_status == "supported"
    assert answer.citations == matches[:3]
    assert "create_order at orders/service.py:12-25 [1]" in answer.text
    assert "save_order at orders/storage.py:8 [2]" in answer.text
    assert "post_order at orders/routes.py:20-31 [3]" in answer.text
    assert "static-analysis" in answer.text
    assert "order_helper" not in answer.text


def test_declines_to_answer_without_source_evidence() -> None:
    answer = compose_grounded_answer("Where is billing?", ())

    assert answer.grounding_status == "insufficient_evidence"
    assert answer.citations == ()
    assert "could not find enough source evidence" in answer.text


@pytest.mark.parametrize("citation_limit", [0, 6])
def test_rejects_unbounded_citation_limits(citation_limit: int) -> None:
    with pytest.raises(ValueError, match="citation_limit must be between 1 and 5"):
        compose_grounded_answer("Where is billing?", (), citation_limit=citation_limit)


def test_rejects_empty_questions() -> None:
    with pytest.raises(ValueError, match="question must not be empty"):
        compose_grounded_answer("   ", ())
