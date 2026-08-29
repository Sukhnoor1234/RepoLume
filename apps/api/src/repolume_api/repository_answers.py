"""Conservative repository answers composed from ranked source evidence."""

from dataclasses import dataclass

from repolume_api.analysis_schemas import GroundingStatus
from repolume_api.evidence_retrieval import EvidenceMatch


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    """Answer text and the exact evidence used to support it."""

    text: str
    grounding_status: GroundingStatus
    citations: tuple[EvidenceMatch, ...]


def _location(match: EvidenceMatch) -> str:
    location = match.node.location
    if location is None:
        raise ValueError("answer citations require source locations")
    lines = str(location.line)
    if location.end_line != location.line:
        lines = f"{lines}-{location.end_line}"
    return f"{location.path}:{lines}"


def compose_grounded_answer(
    question: str,
    matches: tuple[EvidenceMatch, ...],
    *,
    citation_limit: int = 3,
) -> GroundedAnswer:
    """Summarize ranked evidence without claiming behavior the graph cannot prove."""

    if not 1 <= citation_limit <= 5:
        raise ValueError("citation_limit must be between 1 and 5")
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    citations = matches[:citation_limit]
    if not citations:
        return GroundedAnswer(
            text=(
                "RepoLume could not find enough source evidence to answer this question. "
                "Try using a file, module, class, or function name from the architecture map."
            ),
            grounding_status="insufficient_evidence",
            citations=(),
        )

    strongest = citations[0]
    answer_parts = [
        "The strongest available source evidence points to "
        f"{strongest.node.name} at {_location(strongest)} [1]."
    ]
    if len(citations) > 1:
        related = ", ".join(
            f"{match.node.name} at {_location(match)} [{index}]"
            for index, match in enumerate(citations[1:], start=2)
        )
        answer_parts.append(f"Related evidence appears in {related}.")
    answer_parts.append(
        "This summary is based on static-analysis matches; inspect the cited lines to "
        "confirm runtime behavior."
    )
    return GroundedAnswer(
        text=" ".join(answer_parts),
        grounding_status="supported",
        citations=citations,
    )
