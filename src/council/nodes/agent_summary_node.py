"""Agent summary node for independent per-agent discussion summaries."""

from pocketflow import BatchNode

from council.console import print_warning
from council.context import get_agent_messages, get_current_proposals
from council.models import (
    AgentDiscussionSummary,
    DebateAction,
    DebateMessage,
    Persona,
    Proposal,
)
from council.utils import call_llm, parse_json_response


class AgentSummaryNode(BatchNode):
    """BatchNode for summarizing each agent independently after debate."""

    def prep(self, shared):
        """Prepare summarization context for each agent."""
        personas = shared["personas"]
        proposals = shared["proposals"]
        debate_messages = shared.get("debate_messages", [])
        current_proposals = get_current_proposals(proposals, debate_messages)
        initial_proposals = {proposal.agent: proposal for proposal in proposals}

        inputs = []
        for persona in personas:
            inputs.append(
                {
                    "persona": persona,
                    "prompt": shared["prompt"],
                    "initial_proposal": initial_proposals.get(persona.name),
                    "agent_messages": get_agent_messages(
                        persona.name, debate_messages
                    ),
                    "current_proposal": current_proposals.get(persona.name),
                    "debate_messages": debate_messages,
                }
            )

        return inputs

    def exec(self, prep_res):
        """Generate a structured summary for a single agent."""
        persona: Persona = prep_res["persona"]
        initial_proposal = prep_res["initial_proposal"]
        current_proposal = prep_res["current_proposal"]
        agent_messages = prep_res["agent_messages"]
        debate_messages = prep_res["debate_messages"]

        llm_prompt = f"""{persona.to_prompt()}

## Original Question

{prep_res["prompt"]}

## Target Agent

Summarize only {persona.name}.

## Initial Proposal

{self._format_proposal(initial_proposal)}

## Current Reconstructed Proposal

{self._format_proposal(current_proposal)}

## Target Agent Debate Messages

{self._format_messages(agent_messages)}

## Full Debate History For Context

{self._format_messages(debate_messages)}

## Your Task

Create an independent summary of {persona.name}'s discussion history. Do not
blend other agents' positions into this summary except where {persona.name}
explicitly agreed with or responded to them.

Return your response as JSON with this structure:

{{
  "agent": "{persona.name}",
  "initial_position": "Initial position summary",
  "revision_history": ["Revision or stance change"],
  "current_position": "Current position summary",
  "concerns_raised": ["Concern raised by this agent"],
  "agreements": ["Agreement target or agreement detail"],
  "unresolved_concerns": ["Concern still unresolved for this agent"],
  "final_stance": "Final stance based on this agent's latest action"
}}

Use empty lists when there are no items for a list field."""

        response = call_llm(
            llm_prompt,
            temperature=persona.temperature,
            provider=persona.provider,
        )
        parsed = parse_json_response(response)
        return self._summary_from_parsed(parsed, persona.name)

    def exec_fallback(self, prep_res, exc):
        """Generate a deterministic summary when LLM summarization fails."""
        persona = prep_res["persona"]
        print_warning(f"{persona.name} failed to summarize discussion: {exc}")
        return self._fallback_summary(
            persona.name,
            prep_res["initial_proposal"],
            prep_res["current_proposal"],
            prep_res["agent_messages"],
        )

    def post(self, shared, prep_res, exec_res_list):
        """Store per-agent summaries in shared state."""
        shared["agent_summaries"] = [
            result for result in exec_res_list if result is not None
        ]
        return "default"

    def _summary_from_parsed(
        self, parsed: dict, expected_agent: str
    ) -> AgentDiscussionSummary:
        """Validate parsed LLM output and build a summary model."""
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed)}")

        agent = self._required_string(parsed, "agent")
        if agent != expected_agent:
            raise ValueError(f"Expected summary for {expected_agent}, got {agent}")

        return AgentDiscussionSummary(
            agent=agent,
            initial_position=self._required_string(parsed, "initial_position"),
            revision_history=self._string_list(parsed, "revision_history"),
            current_position=self._required_string(parsed, "current_position"),
            concerns_raised=self._string_list(parsed, "concerns_raised"),
            agreements=self._string_list(parsed, "agreements"),
            unresolved_concerns=self._string_list(
                parsed, "unresolved_concerns"
            ),
            final_stance=self._required_string(parsed, "final_stance"),
        )

    def _fallback_summary(
        self,
        agent: str,
        initial_proposal: Proposal | None,
        current_proposal: Proposal | None,
        agent_messages: list[DebateMessage],
    ) -> AgentDiscussionSummary:
        """Build a conservative summary from structured local state."""
        revision_history = []
        concerns_raised = []
        agreements = []

        for message in agent_messages:
            if message.action == DebateAction.REVISE:
                revision_history.append(
                    f"Turn {message.turn}: {message.reasoning}"
                )
            elif message.action == DebateAction.CONCERN:
                concerns_raised.append(message.concern or message.reasoning)
            elif message.action == DebateAction.AGREE:
                agreements.append(message.target or "[No target specified]")

        latest_message = agent_messages[-1] if agent_messages else None
        final_stance = "No debate action recorded."
        if latest_message is not None:
            final_stance = (
                f"Latest action was {latest_message.action.value} on turn "
                f"{latest_message.turn}: {latest_message.reasoning}"
            )

        return AgentDiscussionSummary(
            agent=agent,
            initial_position=(
                initial_proposal.summary
                if initial_proposal is not None
                else "[No initial proposal available]"
            ),
            revision_history=revision_history,
            current_position=(
                current_proposal.summary
                if current_proposal is not None
                else "[No current proposal available]"
            ),
            concerns_raised=concerns_raised,
            agreements=agreements,
            unresolved_concerns=list(concerns_raised),
            final_stance=final_stance,
        )

    def _required_string(self, parsed: dict, key: str) -> str:
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing or invalid '{key}' in response")
        return value.strip()

    def _string_list(self, parsed: dict, key: str) -> list[str]:
        value = parsed.get(key)
        if not isinstance(value, list):
            raise ValueError(f"Missing or invalid '{key}' in response")
        if not all(isinstance(item, str) for item in value):
            raise ValueError(f"Expected strings in '{key}' response list")
        return [item.strip() for item in value if item.strip()]

    def _format_proposal(self, proposal: Proposal | None) -> str:
        if proposal is None:
            return "[No proposal available]"
        return proposal.to_markdown()

    def _format_messages(self, messages: list[DebateMessage]) -> str:
        if not messages:
            return "[No debate messages]"
        return "\n\n".join(message.to_markdown() for message in messages)
