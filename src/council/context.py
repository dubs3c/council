"""Pure helpers for deriving discussion context."""

from council.models import DebateAction, DebateMessage, Proposal, ProposalRevision


def apply_revision(base: Proposal, revision: ProposalRevision) -> Proposal:
    """Apply a partial proposal revision without mutating the base proposal."""
    return Proposal(
        agent=base.agent,
        summary=revision.summary if revision.summary is not None else base.summary,
        analysis=list(
            revision.analysis if revision.analysis is not None else base.analysis
        ),
        recommendations=list(
            revision.recommendations
            if revision.recommendations is not None
            else base.recommendations
        ),
        turn=base.turn,
    )


def get_current_proposals(
    proposals: list[Proposal],
    debate_messages: list[DebateMessage],
) -> dict[str, Proposal]:
    """Reconstruct current proposals from initial proposals and revisions."""
    current = {proposal.agent: proposal for proposal in proposals}

    for message in debate_messages:
        if message.action != DebateAction.REVISE or message.proposal_revision is None:
            continue
        if message.agent not in current:
            raise ValueError(
                f"Cannot apply revision for unknown agent: {message.agent}"
            )
        current[message.agent] = apply_revision(
            current[message.agent], message.proposal_revision
        )

    return current


def get_agent_messages(
    agent: str,
    debate_messages: list[DebateMessage],
) -> list[DebateMessage]:
    """Return debate messages for a single agent in transcript order."""
    return [message for message in debate_messages if message.agent == agent]


def split_debate_messages_for_compaction(
    debate_messages: list[DebateMessage],
    current_turn: int,
    recent_turns_to_keep: int,
) -> tuple[list[DebateMessage], list[DebateMessage], int | None]:
    """Split completed debate messages into compacted and recent ranges."""
    recent_start_turn = max(1, current_turn - recent_turns_to_keep)
    compacted_messages = [
        message for message in debate_messages if message.turn < recent_start_turn
    ]
    recent_messages = [
        message for message in debate_messages if message.turn >= recent_start_turn
    ]
    through_turn = max(
        (message.turn for message in compacted_messages), default=None
    )
    return compacted_messages, recent_messages, through_turn


def summarize_debate_messages_by_agent(
    debate_messages: list[DebateMessage],
) -> dict[str, list[str]]:
    """Create deterministic per-agent summaries for compacted debate context."""
    summaries: dict[str, list[str]] = {}
    for message in debate_messages:
        parts = [f"Turn {message.turn}: {message.action.value}"]
        if message.action == DebateAction.AGREE:
            parts.append(f"agreed with {message.target}")
        elif message.action == DebateAction.CONCERN:
            parts.append(f"concern: {message.concern}")
        elif message.action == DebateAction.REVISE:
            parts.append("revised proposal")
        if message.reasoning:
            parts.append(f"reasoning: {message.reasoning}")
        summaries.setdefault(message.agent, []).append("; ".join(parts))
    return summaries
