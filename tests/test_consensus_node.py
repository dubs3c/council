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
from council.nodes.consensus_node import ConsensusNode


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


def _consensus_response() -> str:
    return json.dumps(
        {
            "summary": "Consensus summary.",
            "strengths": [
                {"point": "Shared strength.", "supporters": ["A", "B"]}
            ],
            "concerns": [],
            "recommendations": [
                {
                    "priority": "high",
                    "action": "Act now.",
                    "rationale": "It matters.",
                }
            ],
            "dissenting_views": [],
        }
    )


def _approval_response() -> str:
    return json.dumps({"approval": True, "feedback": "Looks fair."})


def test_consensus_prompt_uses_agent_summaries_as_separate_sections():
    node = ConsensusNode()
    shared = {
        "prompt": "question",
        "proposals": [_proposal("A", "A initial"), _proposal("B", "B initial")],
        "debate_messages": [
            DebateMessage(
                agent="A",
                turn=1,
                action=DebateAction.REVISE,
                reasoning="updated summary",
                proposal_revision=ProposalRevision(summary="A current"),
            )
        ],
        "agent_summaries": [
            AgentDiscussionSummary(
                agent="A",
                initial_position="A began cautious.",
                revision_history=["A narrowed scope."],
                current_position="A now supports rollout.",
                concerns_raised=["A risk."],
                agreements=[],
                unresolved_concerns=["A unresolved risk."],
                final_stance="Conditional support.",
            ),
            AgentDiscussionSummary(
                agent="B",
                initial_position="B began supportive.",
                revision_history=[],
                current_position="B still supports rollout.",
                concerns_raised=[],
                agreements=["A"],
                unresolved_concerns=[],
                final_stance="Supports A.",
            ),
        ],
        "agreement_map": {"B": "A"},
        "personas": [_persona("A"), _persona("B")],
        "config": {"show_stream": False},
    }

    with patch(
        "council.nodes.consensus_node.call_llm",
        side_effect=[_consensus_response(), _approval_response(), _approval_response()],
    ) as call_llm:
        node.exec(node.prep(shared))

    consensus_prompt = call_llm.call_args_list[0].args[0]
    summaries_section = consensus_prompt.split("## Independent Agent Summaries", 1)[1]

    assert "## Current Proposals By Agent" in consensus_prompt
    assert "A current" in consensus_prompt
    assert "### A" in summaries_section
    assert "A began cautious." in summaries_section
    assert "### B" in summaries_section
    assert "B began supportive." in summaries_section
    assert "## Agreement Map" in consensus_prompt
    assert "- B: A" in consensus_prompt
    assert "## Unresolved Concerns And Dissent" in consensus_prompt
    assert "A unresolved risk." in consensus_prompt


def test_consensus_prompt_falls_back_to_raw_discussion_without_summaries():
    node = ConsensusNode()
    shared = {
        "prompt": "question",
        "proposals": [_proposal("A", "A initial"), _proposal("B", "B initial")],
        "debate_messages": [
            DebateMessage(
                agent="B",
                turn=1,
                action=DebateAction.CONCERN,
                reasoning="raw concern reasoning",
                concern="raw concern",
            )
        ],
        "personas": [_persona("A"), _persona("B")],
        "config": {"show_stream": False},
    }

    with patch(
        "council.nodes.consensus_node.call_llm",
        side_effect=[_consensus_response(), _approval_response(), _approval_response()],
    ) as call_llm:
        node.exec(node.prep(shared))

    consensus_prompt = call_llm.call_args_list[0].args[0]

    assert "## Initial Proposals" in consensus_prompt
    assert "## Debate" in consensus_prompt
    assert "raw concern reasoning" in consensus_prompt
    assert "## Independent Agent Summaries" not in consensus_prompt
