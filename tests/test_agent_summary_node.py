import json
from unittest.mock import patch

from council.models import (
    AgentDiscussionSummary,
    AnalysisPoint,
    DebateAction,
    DebateMessage,
    Persona,
    Proposal,
    ProposalRevision,
)
from council.nodes.agent_summary_node import AgentSummaryNode


def _persona(name: str) -> Persona:
    return Persona(
        name=name,
        role="Reviewer",
        focus="Testing",
        style="Concise",
    )


def _proposal(agent: str, summary: str) -> Proposal:
    return Proposal(
        agent=agent,
        summary=summary,
        analysis=[AnalysisPoint(point=f"{agent} point", reasoning="because")],
        recommendations=[f"{agent} rec"],
    )


def test_exec_parses_agent_summary_without_live_llm():
    node = AgentSummaryNode()
    prep_res = {
        "persona": _persona("A"),
        "prompt": "question",
        "initial_proposal": _proposal("A", "initial"),
        "agent_messages": [],
        "current_proposal": _proposal("A", "current"),
        "debate_messages": [],
    }
    fake_response = json.dumps(
        {
            "agent": "A",
            "initial_position": "Started cautious.",
            "revision_history": ["Narrowed scope."],
            "current_position": "Now supports rollout.",
            "concerns_raised": ["Testing risk."],
            "agreements": ["B"],
            "unresolved_concerns": [],
            "final_stance": "Supports the current proposal.",
        }
    )

    with patch(
        "council.nodes.agent_summary_node.call_llm", return_value=fake_response
    ):
        summary = node.exec(prep_res)

    assert isinstance(summary, AgentDiscussionSummary)
    assert summary.agent == "A"
    assert summary.initial_position == "Started cautious."
    assert summary.revision_history == ["Narrowed scope."]
    assert summary.current_position == "Now supports rollout."
    assert summary.concerns_raised == ["Testing risk."]
    assert summary.agreements == ["B"]
    assert summary.unresolved_concerns == []
    assert summary.final_stance == "Supports the current proposal."


def test_prep_and_post_create_one_summary_per_persona():
    node = AgentSummaryNode()
    personas = [_persona("A"), _persona("B")]
    shared = {
        "prompt": "question",
        "personas": personas,
        "proposals": [_proposal("A", "A initial"), _proposal("B", "B initial")],
        "debate_messages": [
            DebateMessage(
                agent="A",
                turn=1,
                action=DebateAction.REVISE,
                reasoning="update",
                proposal_revision=ProposalRevision(summary="A current"),
            ),
            DebateMessage(
                agent="B",
                turn=1,
                action=DebateAction.AGREE,
                reasoning="agree",
                target="A",
            ),
        ],
    }

    prep_res = node.prep(shared)

    assert [item["persona"].name for item in prep_res] == ["A", "B"]
    assert prep_res[0]["agent_messages"][0].agent == "A"
    assert prep_res[0]["current_proposal"].summary == "A current"

    summaries = [
        AgentDiscussionSummary(
            agent="A",
            initial_position="A initial",
            revision_history=[],
            current_position="A current",
            concerns_raised=[],
            agreements=[],
            unresolved_concerns=[],
            final_stance="stance",
        ),
        AgentDiscussionSummary(
            agent="B",
            initial_position="B initial",
            revision_history=[],
            current_position="B initial",
            concerns_raised=[],
            agreements=["A"],
            unresolved_concerns=[],
            final_stance="stance",
        ),
    ]

    action = node.post(shared, prep_res, summaries)

    assert action == "default"
    assert shared["agent_summaries"] == summaries


def test_fallback_summary_uses_local_state_deterministically():
    node = AgentSummaryNode()
    prep_res = {
        "persona": _persona("A"),
        "initial_proposal": _proposal("A", "initial summary"),
        "current_proposal": _proposal("A", "current summary"),
        "agent_messages": [
            DebateMessage(
                agent="A",
                turn=1,
                action=DebateAction.CONCERN,
                reasoning="risk reasoning",
                concern="deployment risk",
            ),
            DebateMessage(
                agent="A",
                turn=2,
                action=DebateAction.REVISE,
                reasoning="added rollout guardrail",
                proposal_revision=ProposalRevision(summary="current summary"),
            ),
            DebateMessage(
                agent="A",
                turn=3,
                action=DebateAction.AGREE,
                reasoning="aligned",
                target="B",
            ),
        ],
    }

    summary = node.exec_fallback(prep_res, ValueError("bad response"))

    assert summary.agent == "A"
    assert summary.initial_position == "initial summary"
    assert summary.current_position == "current summary"
    assert summary.revision_history == ["Turn 2: added rollout guardrail"]
    assert summary.concerns_raised == ["deployment risk"]
    assert summary.agreements == ["B"]
    assert summary.unresolved_concerns == ["deployment risk"]
    assert summary.final_stance == "Latest action was agree on turn 3: aligned"
