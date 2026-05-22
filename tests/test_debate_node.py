import json
from unittest.mock import patch

from council.context import apply_revision, get_current_proposals
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
    base = Proposal(
        agent="A",
        summary="old summary",
        analysis=[AnalysisPoint(point="p1", reasoning="r1")],
        recommendations=["rec-1"],
        turn=0,
    )

    revised = apply_revision(
        base,
        ProposalRevision(summary="new summary"),
    )

    assert revised.summary == "new summary"
    assert revised.analysis == base.analysis
    assert revised.recommendations == base.recommendations


def test_get_latest_proposal_reconstructs_from_partial_revisions():
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

    latest = get_current_proposals([base], messages)["A"]

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


def test_prep_compacts_prompt_context_without_mutating_debate_messages():
    node = DebateNode()
    debate_messages = [
        DebateMessage(
            agent="A",
            turn=turn,
            action=DebateAction.CONCERN,
            reasoning=f"raw reasoning {turn}",
            concern=f"raw concern {turn}",
        )
        for turn in range(1, 12)
    ]
    shared = {
        "personas": [_persona("A")],
        "proposals": [
            Proposal(
                agent="A",
                summary="initial summary",
                analysis=[AnalysisPoint(point="initial point", reasoning="because")],
                recommendations=["initial rec"],
            )
        ],
        "debate_messages": list(debate_messages),
        "current_turn": 11,
        "prompt": "question",
        "config": {
            "show_stream": False,
            "context_compaction_enabled": True,
            "compact_after_turns": 8,
            "recent_turns_to_keep": 3,
        },
    }

    prep_res = node.prep(shared)[0]
    prompt_context = prep_res["proposals_context"]

    assert shared["debate_messages"] == debate_messages
    assert shared["compacted_context"]["through_turn"] == 8
    assert "## Initial Proposals" in prompt_context
    assert "## Current Proposals" in prompt_context
    assert "## Older Debate Summary By Agent" in prompt_context
    assert "## Recent Debate" in prompt_context
    assert "**A** (Turn 8)" not in prompt_context
    assert "Turn 8: concern" in prompt_context
    assert "**A** (Turn 9)" in prompt_context
    assert "**A** (Turn 11)" in prompt_context


def test_post_populates_agreement_map_from_latest_actions():
    node = DebateNode()
    shared = {
        "personas": [_persona("A"), _persona("B"), _persona("C")],
        "debate_messages": [
            DebateMessage(
                agent="B",
                turn=1,
                action=DebateAction.AGREE,
                reasoning="initially agrees",
                target="A",
            )
        ],
        "current_turn": 1,
        "config": {"max_turns": 3, "show_stream": False},
    }

    result = node.post(
        shared,
        prep_res=None,
        exec_res_list=[
            {
                "message": DebateMessage(
                    agent="B",
                    turn=2,
                    action=DebateAction.CONCERN,
                    reasoning="withdraws agreement",
                    concern="new risk",
                )
            },
            {
                "message": DebateMessage(
                    agent="C",
                    turn=2,
                    action=DebateAction.AGREE,
                    reasoning="supports A",
                    target="A",
                )
            },
        ],
    )

    assert result == "continue"
    assert shared["agreement_map"] == {"C": "A"}
