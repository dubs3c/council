from council.models import (
    AgentDiscussionSummary,
    AnalysisPoint,
    DebateAction,
    DebateMessage,
    Persona,
    Proposal,
    ProposalRevision,
)
from council.nodes.output_node import OutputNode


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


def _shared(output_dir: str, debate_messages: list[DebateMessage]) -> dict:
    return {
        "prompt": "question",
        "personas": [_persona("A"), _persona("B")],
        "proposals": [_proposal("A", "A initial"), _proposal("B", "B initial")],
        "debate_messages": debate_messages,
        "final_report": None,
        "config": {"output_dir": output_dir, "show_stream": False},
    }


def test_report_includes_separated_agent_summaries(tmp_path):
    node = OutputNode()
    shared = _shared(str(tmp_path), [])
    shared["agent_summaries"] = [
        AgentDiscussionSummary(
            agent="A",
            initial_position="A summary initial.",
            revision_history=["A changed scope."],
            current_position="A summary current.",
            concerns_raised=["A risk."],
            agreements=[],
            unresolved_concerns=["A unresolved."],
            final_stance="A supports conditionally.",
        ),
        AgentDiscussionSummary(
            agent="B",
            initial_position="B summary initial.",
            revision_history=[],
            current_position="B summary current.",
            concerns_raised=[],
            agreements=["A"],
            unresolved_concerns=[],
            final_stance="B supports A.",
        ),
    ]

    content = node.exec(node.prep(shared))["content"]
    a_section = content.split("### A", 1)[1].split("### B", 1)[0]
    b_section = content.split("### B", 1)[1].split("---", 1)[0]

    assert "## Independent Agent Summaries" in content
    assert "A summary initial." in a_section
    assert "A changed scope." in a_section
    assert "B summary initial." not in a_section
    assert "B summary initial." in b_section
    assert "- A" in b_section
    assert "A summary initial." not in b_section


def test_report_preserves_complete_transcript_and_revision_labels(tmp_path):
    node = OutputNode()
    debate_messages = [
        DebateMessage(
            agent="A",
            turn=1,
            action=DebateAction.REVISE,
            reasoning="summary-only revision reasoning",
            proposal_revision=ProposalRevision(summary="A refined summary"),
        ),
        DebateMessage(
            agent="B",
            turn=1,
            action=DebateAction.CONCERN,
            reasoning="concern reasoning",
            concern="deployment risk",
        ),
        DebateMessage(
            agent="A",
            turn=2,
            action=DebateAction.AGREE,
            reasoning="agreement reasoning",
            target="B",
        ),
    ]
    shared = _shared(str(tmp_path), debate_messages)

    content = node.exec(node.prep(shared))["content"]
    transcript = content.split("Full Discussion Transcript", 1)[1]

    assert shared["debate_messages"] == debate_messages
    assert "### Initial Proposals" in transcript
    assert "### Debate Rounds" in transcript
    assert "summary-only revision reasoning" in transcript
    assert "Proposal revision:" in transcript
    assert "- Summary: A refined summary" in transcript
    assert "A refined summary" not in content.split("Proposal revision:", 1)[0]
    assert "concern reasoning" in transcript
    assert "deployment risk" in transcript
    assert "agreement reasoning" in transcript
    assert "Agrees with **B**" in transcript


def test_compaction_note_only_appears_when_context_present(tmp_path):
    node = OutputNode()
    shared = _shared(str(tmp_path), [])

    without_note = node.exec(node.prep(shared))["content"]
    shared["compacted_context"] = {"older_turns": "summarized"}
    with_note = node.exec(node.prep(shared))["content"]

    assert "## Context Compaction Note" not in without_note
    assert "## Context Compaction Note" in with_note
    assert "The full discussion transcript below remains complete." in with_note
