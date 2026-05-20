import json
from unittest.mock import patch

from council.models import (
    AnalysisPoint,
    DebateAction,
    DebateMessage,
    Persona,
    Proposal,
    ProposalRevision,
)
from council.nodes.debate_node import DebateNode


def _persona(name: str) -> Persona:
    return Persona(
        name=name,
        role="Reviewer",
        focus="Testing",
        style="Concise",
    )


def test_apply_partial_revision_keeps_unchanged_fields():
    node = DebateNode()
    base = Proposal(
        agent="A",
        summary="old summary",
        analysis=[AnalysisPoint(point="p1", reasoning="r1")],
        recommendations=["rec-1"],
        turn=0,
    )

    revised = node._apply_revision(
        base,
        ProposalRevision(summary="new summary"),
    )

    assert revised.summary == "new summary"
    assert revised.analysis == base.analysis
    assert revised.recommendations == base.recommendations


def test_get_latest_proposal_reconstructs_from_partial_revisions():
    node = DebateNode()
    base = Proposal(
        agent="A",
        summary="summary v1",
        analysis=[AnalysisPoint(point="p1", reasoning="r1")],
        recommendations=["rec-1"],
        turn=0,
    )

    messages = [
        DebateMessage(
            agent="A",
            turn=1,
            action=DebateAction.REVISE,
            reasoning="update summary",
            proposal_revision=ProposalRevision(summary="summary v2"),
        ),
        DebateMessage(
            agent="A",
            turn=2,
            action=DebateAction.REVISE,
            reasoning="update recs",
            proposal_revision=ProposalRevision(recommendations=["rec-2"]),
        ),
    ]

    latest = node._get_latest_proposal("A", [base], messages)

    assert latest is not None
    assert latest.summary == "summary v2"
    assert latest.analysis == base.analysis
    assert latest.recommendations == ["rec-2"]


def test_exec_parses_revision_without_live_llm():
    node = DebateNode()
    prep_res = {
        "persona": _persona("A"),
        "proposals_context": "context",
        "current_turn": 1,
        "prompt": "question",
        "show_stream": False,
    }

    fake_response = json.dumps(
        {
            "action": "revise",
            "reasoning": "Refining scope",
            "proposal_revision": {"summary": "narrowed summary"},
        }
    )

    with patch("council.nodes.debate_node.call_llm", return_value=fake_response):
        result = node.exec(prep_res)

    message = result["message"]
    assert message.action == DebateAction.REVISE
    assert message.proposal_revision is not None
    assert message.proposal_revision.summary == "narrowed summary"
    assert message.proposal_revision.analysis is None
    assert message.proposal_revision.recommendations is None
