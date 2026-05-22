"""Data models for The Council multi-agent discussion system."""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DebateAction(Enum):
    """Actions an agent can take during debate."""

    REVISE = "revise"
    AGREE = "agree"
    CONCERN = "concern"


class ApprovalStatus(Enum):
    """Agent's response to consensus draft."""

    APPROVE = "approve"
    FEEDBACK = "feedback"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider.

    Each agent can use a different provider, model, and API key.
    This enables mixing providers (e.g., one agent uses GPT-4, another uses Claude).

    Attributes:
        api_key: API key or env var reference (e.g., "$OPENAI_API_KEY")
        base_url: Base URL for OpenAI-compatible API
        model: Model identifier (e.g., "gpt-4o", "claude-3-opus-20240229")
        prompt_cache: Whether prompt caching is enabled when safely supported
        prompt_cache_strategy: Provider-safe prompt cache strategy
    """

    api_key: str = "$OPENAI_API_KEY"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    prompt_cache: bool = False
    prompt_cache_strategy: str = "none"

    def get_api_key(self) -> str:
        """Resolve API key, supporting environment variable references."""
        if self.api_key.startswith("$"):
            env_var = self.api_key[1:]
            key = os.environ.get(env_var)
            if not key:
                raise ValueError(f"Environment variable {env_var} not set")
            return key
        return self.api_key


# Default provider configuration
DEFAULT_PROVIDER = ProviderConfig()


@dataclass
class Persona:
    """Defines an agent's personality, behavior, and LLM provider.

    Each persona can be configured with:
    - Personality traits (name, role, focus, style)
    - LLM settings (temperature)
    - Provider configuration (api_key, base_url, model)
    """

    name: str
    role: str
    focus: str
    style: str
    temperature: float = 0.7
    provider: ProviderConfig = field(default_factory=ProviderConfig)

    def to_prompt(self) -> str:
        """Format persona for inclusion in LLM prompts."""
        return f"""You are {self.name}, a {self.role}.

Your focus: {self.focus}

Your style: {self.style}

Stay in character throughout the discussion. Your analysis should reflect your unique perspective."""


@dataclass
class AnalysisPoint:
    """A single point of analysis with reasoning."""

    point: str
    reasoning: str


@dataclass
class Proposal:
    """An agent's proposal during discussion."""

    agent: str
    summary: str
    analysis: List[AnalysisPoint]
    recommendations: List[str]
    turn: int = 0

    def to_markdown(self) -> str:
        """Format proposal as markdown."""
        lines = [
            f"### {self.agent}'s Proposal",
            "",
            f"**Summary:** {self.summary}",
            "",
            "**Analysis:**",
        ]
        for point in self.analysis:
            lines.append(f"- {point.point}")
            lines.append(f"  - *Reasoning:* {point.reasoning}")

        lines.append("")
        lines.append("**Recommendations:**")
        for rec in self.recommendations:
            lines.append(f"- {rec}")

        return "\n".join(lines)


@dataclass
class ProposalRevision:
    """A partial revision to an agent's existing proposal."""

    summary: Optional[str] = None
    analysis: Optional[List[AnalysisPoint]] = None
    recommendations: Optional[List[str]] = None


@dataclass
class DebateMessage:
    """A message in the debate phase."""

    agent: str
    turn: int
    action: DebateAction
    reasoning: str
    target: Optional[str] = (
        None  # For AGREE action - which agent they agree with
    )
    proposal_revision: Optional[ProposalRevision] = None  # For REVISE action
    concern: Optional[str] = None  # For CONCERN action

    def to_markdown(self) -> str:
        """Format debate message as markdown."""
        lines = [f"**{self.agent}** (Turn {self.turn}) - *{self.action.value}*"]

        if self.action == DebateAction.AGREE:
            lines.append(f"> Agrees with **{self.target}**")
        elif self.action == DebateAction.CONCERN:
            lines.append(f"> Raises concern: {self.concern}")

        lines.append(f"> {self.reasoning}")

        if self.proposal_revision:
            lines.append("")
            lines.append("Proposal revision:")
            if self.proposal_revision.summary is not None:
                lines.append(f"- Summary: {self.proposal_revision.summary}")
            if self.proposal_revision.analysis is not None:
                lines.append("- Analysis updates:")
                for point in self.proposal_revision.analysis:
                    lines.append(f"  - {point.point}")
                    lines.append(f"    - *Reasoning:* {point.reasoning}")
            if self.proposal_revision.recommendations is not None:
                lines.append("- Recommendations updates:")
                for rec in self.proposal_revision.recommendations:
                    lines.append(f"  - {rec}")

        return "\n".join(lines)


@dataclass
class AgentDiscussionSummary:
    """Structured summary of one agent's discussion history."""

    agent: str
    initial_position: str
    revision_history: List[str]
    current_position: str
    concerns_raised: List[str]
    agreements: List[str]
    unresolved_concerns: List[str]
    final_stance: str


@dataclass
class ConsensusPoint:
    """A point of consensus with supporters."""

    point: str
    supporters: List[str]


@dataclass
class Recommendation:
    """A prioritized recommendation."""

    priority: str  # "high", "medium", "low"
    action: str
    rationale: str


@dataclass
class DissentingView:
    """A view that couldn't be reconciled."""

    agent: str
    position: str


@dataclass
class ConcernResolution:
    """A concern and how it was resolved."""

    concern: str
    raised_by: str
    resolution: str


@dataclass
class ConsensusReport:
    """The final consensus report."""

    summary: str
    strengths: List[ConsensusPoint]
    concerns: List[ConcernResolution]
    recommendations: List[Recommendation]
    dissenting_views: List[DissentingView] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Format consensus report as markdown."""
        lines = [
            "## Consensus Summary",
            "",
            self.summary,
            "",
            "## Strengths",
            "",
        ]

        for strength in self.strengths:
            supporters = ", ".join(strength.supporters)
            lines.append(f"- {strength.point}")
            lines.append(f"  - *Agreed by: {supporters}*")

        lines.append("")
        lines.append("## Concerns & Resolutions")
        lines.append("")

        if self.concerns:
            lines.append("| Concern | Raised By | Resolution |")
            lines.append("|---------|-----------|------------|")
            for c in self.concerns:
                lines.append(
                    f"| {c.concern} | {c.raised_by} | {c.resolution} |"
                )
        else:
            lines.append("*No major concerns raised.*")

        lines.append("")
        lines.append("## Recommendations")
        lines.append("")

        # Group by priority
        for priority in ["high", "medium", "low"]:
            priority_recs = [
                r for r in self.recommendations if r.priority == priority
            ]
            if priority_recs:
                lines.append(f"### {priority.capitalize()} Priority")
                lines.append("")
                for rec in priority_recs:
                    lines.append(f"- **{rec.action}**")
                    lines.append(f"  - *Rationale:* {rec.rationale}")
                lines.append("")

        if self.dissenting_views:
            lines.append("## Dissenting Views")
            lines.append("")
            for view in self.dissenting_views:
                lines.append(f"- **{view.agent}:** {view.position}")

        return "\n".join(lines)


@dataclass
class DiscussionState:
    """Tracks the state of the entire discussion."""

    prompt: str
    file_content: Optional[str] = None
    file_path: Optional[str] = None
    personas: List[Persona] = field(default_factory=list)
    proposals: List[Proposal] = field(default_factory=list)
    debate_messages: List[DebateMessage] = field(default_factory=list)
    current_turn: int = 0
    consensus_reached: bool = False
    final_report: Optional[ConsensusReport] = None

    def get_current_proposals(self) -> dict:
        """Get the most recent proposal from each agent."""
        from council.context import get_current_proposals

        return get_current_proposals(self.proposals, self.debate_messages)

    def get_agreements(self) -> dict:
        """Get which agents agree with which proposals."""
        agreements = {}
        for msg in self.debate_messages:
            if msg.action == DebateAction.AGREE:
                agreements[msg.agent] = msg.target
        return agreements

    def check_consensus(self) -> bool:
        """Check if all agents have agreed on the same proposal."""
        if not self.proposals:
            return False

        agreements = self.get_agreements()
        agents = [p.name for p in self.personas]

        # If we have fewer agreements than agents-1, no consensus yet
        # (one agent's proposal, others agree)
        if len(agreements) < len(agents) - 1:
            return False

        # Check if all agreeing agents point to the same target
        targets = set(agreements.values())
        if len(targets) == 1:
            # Check the target agent isn't also agreeing with someone else
            target = list(targets)[0]
            if target not in agreements:
                return True

        return False

    def to_transcript_markdown(self) -> str:
        """Generate full discussion transcript as markdown."""
        lines = [
            "## Discussion Transcript",
            "",
            "### Initial Proposals",
            "",
        ]

        for proposal in self.proposals:
            if proposal.turn == 0:
                lines.append(proposal.to_markdown())
                lines.append("")

        if self.debate_messages:
            lines.append("### Debate")
            lines.append("")

            current_turn = 0
            for msg in self.debate_messages:
                if msg.turn != current_turn:
                    current_turn = msg.turn
                    lines.append("---")
                    lines.append(f"#### Turn {current_turn}")
                    lines.append("")

                lines.append(msg.to_markdown())
                lines.append("")

        return "\n".join(lines)
