import pytest

from council.context import (
    apply_revision,
    get_agent_messages,
    get_current_proposals,
    split_debate_messages_for_compaction,
)
from council.models import (
    AnalysisPoint,
    DebateAction,
    DebateMessage,
    DiscussionState,
    Proposal,
    ProposalRevision,
)


def _proposal(agent: str, summary: str) -> Proposal:
    return Proposal(
        agent=agent,
        summary=summary,
        analysis=[AnalysisPoint(point=f"{agent} point", reasoning="because")],
        recommendations=[f"{agent} rec"],
    )


def test_apply_revision_preserves_omitted_fields_without_mutating_base():
    base = _proposal("A", "old summary")

    revised = apply_revision(base, ProposalRevision(summary="new summary"))

    assert revised is not base
    assert revised.summary == "new summary"
    assert revised.analysis == base.analysis
    assert revised.analysis is not base.analysis
    assert revised.recommendations == base.recommendations
    assert revised.recommendations is not base.recommendations
    assert base.summary == "old summary"


def test_apply_revision_replaces_full_list_fields_when_present():
    base = _proposal("A", "old summary")
    new_analysis = [AnalysisPoint(point="new point", reasoning="new reason")]
    new_recommendations = ["new rec"]

    revised = apply_revision(
        base,
        ProposalRevision(
            analysis=new_analysis,
            recommendations=new_recommendations,
        ),
    )

    assert revised.summary == "old summary"
    assert revised.analysis == new_analysis
    assert revised.analysis is not new_analysis
    assert revised.recommendations == new_recommendations
    assert revised.recommendations is not new_recommendations
    assert base.analysis != new_analysis
    assert base.recommendations != new_recommendations


def test_get_current_proposals_applies_revisions_in_order_per_agent():
    proposals = [_proposal("A", "A v1"), _proposal("B", "B v1")]
    messages = [
        DebateMessage(
            agent="A",
            turn=1,
            action=DebateAction.REVISE,
            reasoning="summary",
            proposal_revision=ProposalRevision(summary="A v2"),
        ),
        DebateMessage(
            agent="B",
            turn=1,
            action=DebateAction.REVISE,
            reasoning="recommendations",
            proposal_revision=ProposalRevision(recommendations=["B rec v2"]),
        ),
        DebateMessage(
            agent="A",
            turn=2,
            action=DebateAction.REVISE,
            reasoning="recommendations",
            proposal_revision=ProposalRevision(recommendations=["A rec v3"]),
        ),
    ]

    current = get_current_proposals(proposals, messages)

    assert current["A"].summary == "A v2"
    assert current["A"].analysis == proposals[0].analysis
    assert current["A"].recommendations == ["A rec v3"]
    assert current["B"].summary == "B v1"
    assert current["B"].recommendations == ["B rec v2"]


def test_get_current_proposals_rejects_unknown_agent_revision():
    messages = [
        DebateMessage(
            agent="missing",
            turn=1,
            action=DebateAction.REVISE,
            reasoning="unknown",
            proposal_revision=ProposalRevision(summary="new"),
        )
    ]

    with pytest.raises(ValueError, match="unknown agent"):
        get_current_proposals([_proposal("A", "A v1")], messages)


def test_get_agent_messages_returns_only_matching_agent_in_order():
    messages = [
        DebateMessage(
            agent="A",
            turn=1,
            action=DebateAction.CONCERN,
            reasoning="first",
            concern="risk",
        ),
        DebateMessage(
            agent="B",
            turn=1,
            action=DebateAction.AGREE,
            reasoning="agree",
            target="A",
        ),
        DebateMessage(
            agent="A",
            turn=2,
            action=DebateAction.REVISE,
            reasoning="second",
            proposal_revision=ProposalRevision(summary="A v2"),
        ),
    ]

    agent_messages = get_agent_messages("A", messages)

    assert [message.reasoning for message in agent_messages] == ["first", "second"]


def test_split_debate_messages_for_compaction_uses_completed_turn_boundary():
    messages = [
        DebateMessage(
            agent="A",
            turn=turn,
            action=DebateAction.CONCERN,
            reasoning=f"reasoning {turn}",
            concern=f"concern {turn}",
        )
        for turn in range(1, 12)
    ]

    compacted, recent, through_turn = split_debate_messages_for_compaction(
        messages,
        current_turn=12,
        recent_turns_to_keep=3,
    )

    assert through_turn == 8
    assert [message.turn for message in compacted] == list(range(1, 9))
    assert [message.turn for message in recent] == [9, 10, 11]


def test_discussion_state_get_current_proposals_uses_revisions():
    state = DiscussionState(
        prompt="question",
        proposals=[_proposal("A", "A v1")],
        debate_messages=[
            DebateMessage(
                agent="A",
                turn=1,
                action=DebateAction.REVISE,
                reasoning="update",
                proposal_revision=ProposalRevision(summary="A v2"),
            )
        ],
    )

    current = state.get_current_proposals()

    assert current["A"].summary == "A v2"
    assert current["A"].recommendations == ["A rec"]
