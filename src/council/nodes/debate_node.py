"""Debate node for agent discussion and revision."""

from pocketflow import BatchNode

from council.console import (
    print_debate_message,
    print_debate_turn,
    print_special_event,
    print_warning,
)
from council.context import (
    get_current_proposals,
    split_debate_messages_for_compaction,
    summarize_debate_messages_by_agent,
)
from council.models import (
    AnalysisPoint,
    DebateAction,
    DebateMessage,
    Persona,
    Proposal,
    ProposalRevision,
)
from council.utils import call_llm, parse_json_response


CONTEXT_COMPACTION_ENABLED = True
COMPACT_AFTER_TURNS = 8
RECENT_TURNS_TO_KEEP = 3


class DebateNode(BatchNode):
    """BatchNode for debate rounds.

    Each agent reviews all current proposals and can:
    - Revise their own proposal
    - Agree with another agent's proposal
    - Raise a new concern

    Returns action to control flow:
    - "continue": More debate needed
    - "consensus_ready": All agents agree
    - "max_turns": Max turns reached
    """

    def prep(self, shared):
        """Prepare debate context for each agent."""
        personas = shared["personas"]
        proposals = shared["proposals"]
        debate_messages = shared.get("debate_messages", [])
        current_turn = shared.get("current_turn", 0) + 1
        current_proposals = get_current_proposals(proposals, debate_messages)
        config = shared["config"]
        compacted_context = self._prepare_compacted_context(
            shared, debate_messages, current_turn
        )
        prompt_messages = (
            compacted_context["recent_messages"]
            if compacted_context is not None
            else debate_messages
        )

        # Format discussion context for the prompt without mutating the transcript.
        proposals_context = self._format_discussion_context(
            proposals,
            current_proposals,
            compacted_context,
            prompt_messages,
        )

        # Create input for each persona
        inputs = []
        for persona in personas:
            inputs.append(
                {
                    "persona": persona,
                    "proposals_context": proposals_context,
                    "current_turn": current_turn,
                    "prompt": shared["prompt"],
                    "show_stream": config["show_stream"],
                    "own_proposal": current_proposals.get(persona.name),
                }
            )

        return inputs

    def _prepare_compacted_context(
        self,
        shared: dict,
        debate_messages: list[DebateMessage],
        current_turn: int,
    ) -> dict | None:
        """Derive compacted prompt context while preserving full messages."""
        config = shared["config"]
        if not config.get("context_compaction_enabled", CONTEXT_COMPACTION_ENABLED):
            return None

        compact_after_turns = config.get("compact_after_turns", COMPACT_AFTER_TURNS)
        if current_turn <= compact_after_turns:
            return None

        recent_turns_to_keep = config.get(
            "recent_turns_to_keep", RECENT_TURNS_TO_KEEP
        )
        compacted_messages, recent_messages, through_turn = (
            split_debate_messages_for_compaction(
                debate_messages, current_turn, recent_turns_to_keep
            )
        )
        if through_turn is None:
            return None

        compacted_context = {
            "through_turn": through_turn,
            "recent_turns_to_keep": recent_turns_to_keep,
            "summary_by_agent": summarize_debate_messages_by_agent(
                compacted_messages
            ),
            "recent_messages": recent_messages,
        }
        shared["compacted_context"] = {
            key: value
            for key, value in compacted_context.items()
            if key != "recent_messages"
        }
        return compacted_context

    def _format_discussion_context(
        self,
        initial_proposals: list[Proposal],
        current_proposals: dict[str, Proposal],
        compacted_context: dict | None,
        debate_messages: list[DebateMessage],
    ) -> str:
        """Format proposals and debate context for the debate prompt."""
        lines = ["## Initial Proposals\n"]

        for proposal in initial_proposals:
            lines.append(proposal.to_markdown())
            lines.append("")

        lines.append("\n## Current Proposals\n")

        for proposal in current_proposals.values():
            lines.append(proposal.to_markdown())
            lines.append("")

        if compacted_context is not None:
            lines.append("\n## Older Debate Summary By Agent\n")
            lines.append(
                "Compacted completed debate turns through "
                f"turn {compacted_context['through_turn']}."
            )
            lines.append("")
            for agent, summaries in compacted_context[
                "summary_by_agent"
            ].items():
                lines.append(f"### {agent}")
                for summary in summaries:
                    lines.append(f"- {summary}")
                lines.append("")

        if debate_messages:
            heading = (
                "Recent Debate" if compacted_context is not None else "Debate History"
            )
            lines.append(f"\n## {heading}\n")
            for msg in debate_messages:
                lines.append(msg.to_markdown())
                lines.append("")

        return "\n".join(lines)

    def exec(self, prep_res):
        """Generate debate response for a single agent."""
        persona: Persona = prep_res["persona"]
        proposals_context = prep_res["proposals_context"]
        current_turn = prep_res["current_turn"]
        prompt = prep_res["prompt"]

        # Get list of other agents

        llm_prompt = f"""{persona.to_prompt()}

## Discussion Context

Original question: {prompt}

{proposals_context}

## Your Task (Turn {current_turn})

Review the proposals and debate above. You must choose ONE of these actions:

1. **REVISE** - Update your own proposal based on others' input
2. **AGREE** - Fully endorse another agent's proposal (specify which agent)
3. **CONCERN** - Raise a new concern that hasn't been addressed

Choose based on:
- If you see merit in another's proposal that addresses your concerns better, AGREE with them
- If you want to incorporate feedback or respond to concerns, REVISE your proposal
- If you see an unaddressed issue, raise a CONCERN

Return your response as JSON with this structure:

{{
  "action": "revise",
  "target": "The Architect",
  "reasoning": "Explain your thinking. Why are you taking this action?",
  "concern": "Only if action is concern - describe the unaddressed issue",
  "proposal_revision": {{
    "summary": "Optional: revised summary",
    "analysis": [{{"point": "Optional: replacement analysis point", "reasoning": "Why it matters"}}],
    "recommendations": ["Optional: replacement recommendation"]
  }}
}}

Notes:
- action: "revise", "agree", or "concern"
- target: Required only if action is "agree" - which agent you agree with
- concern: Required only if action is "concern"
- proposal_revision: Required only if action is "revise". Include ONLY fields you changed.
- Revision semantics:
  - Included summary replaces the prior summary.
  - Included analysis replaces the full prior analysis list.
  - Included recommendations replaces the full prior recommendations list.
  - Omitted fields remain unchanged.

Be constructive. The goal is to reach consensus, not to win."""

        response = call_llm(
            llm_prompt,
            temperature=persona.temperature,
            provider=persona.provider,
        )

        # Parse JSON response
        parsed = parse_json_response(response)

        # Validate action
        action_str = parsed.get("action", "").lower()
        if action_str not in ["revise", "agree", "concern"]:
            raise ValueError(f"Invalid action: {action_str}")

        action = DebateAction(action_str)

        # Build DebateMessage
        message = DebateMessage(
            agent=persona.name,
            turn=current_turn,
            action=action,
            reasoning=parsed.get("reasoning", "").strip(),
        )

        if action == DebateAction.AGREE:
            message.target = parsed.get("target", "").strip()
            if not message.target:
                raise ValueError("AGREE action requires 'target' field")

        elif action == DebateAction.CONCERN:
            message.concern = parsed.get("concern", "").strip()
            if not message.concern:
                raise ValueError("CONCERN action requires 'concern' field")

        elif action == DebateAction.REVISE:
            updated = parsed.get("proposal_revision", {})
            if not updated or not isinstance(updated, dict):
                raise ValueError(
                    "REVISE action requires 'proposal_revision' field"
                )

            analysis_update = None
            if "analysis" in updated:
                analysis_points = []
                for item in updated.get("analysis", []):
                    analysis_points.append(
                        AnalysisPoint(
                            point=item["point"], reasoning=item["reasoning"]
                        )
                    )
                analysis_update = analysis_points

            message.proposal_revision = ProposalRevision(
                summary=(
                    updated.get("summary", "").strip()
                    if "summary" in updated
                    else None
                ),
                analysis=analysis_update,
                recommendations=(
                    updated.get("recommendations", [])
                    if "recommendations" in updated
                    else None
                ),
            )

        return {
            "message": message,
            "persona_name": persona.name,
            "show_stream": prep_res["show_stream"],
        }

    def exec_fallback(self, prep_res, exc):
        """Handle LLM failures gracefully."""
        persona = prep_res["persona"]
        print_warning(f"{persona.name} failed in debate: {exc}")

        # Return a minimal response - just maintain current position
        return {
            "message": DebateMessage(
                agent=persona.name,
                turn=prep_res["current_turn"],
                action=DebateAction.CONCERN,
                reasoning="[Error occurred during debate]",
                concern=str(exc),
            ),
            "persona_name": persona.name,
            "show_stream": prep_res["show_stream"],
        }

    def post(self, shared, prep_res, exec_res_list):
        """Process debate responses and determine next action."""
        current_turn = shared.get("current_turn", 0) + 1
        shared["current_turn"] = current_turn
        max_turns = shared["config"]["max_turns"]
        show_stream = shared["config"]["show_stream"]

        if show_stream:
            print_debate_turn(current_turn)

        # Collect all debate messages
        new_messages = []
        for result in exec_res_list:
            if result and result.get("message"):
                message = result["message"]
                new_messages.append(message)
                shared["debate_messages"].append(message)

                if show_stream:
                    print_debate_message(message.agent, message.to_markdown())

        # Check for consensus
        if self._check_consensus(shared):
            shared["consensus_reached"] = True
            if show_stream:
                print_special_event(f"CONSENSUS REACHED at Turn {current_turn}")
            return "consensus_ready"

        # Check if max turns reached
        if current_turn >= max_turns:
            if show_stream:
                print_special_event(f"MAX TURNS ({max_turns}) REACHED")
            return "max_turns"

        # Continue debate
        return "continue"

    def _check_consensus(self, shared) -> bool:
        """Check if all agents have agreed on the same proposal."""
        personas = shared["personas"]
        debate_messages = shared.get("debate_messages", [])

        if not debate_messages:
            return False

        # Get the most recent action from each agent
        latest_actions = {msg.agent: msg for msg in debate_messages}

        # Count agreements
        agreements = {}
        for agent, msg in latest_actions.items():
            if msg.action == DebateAction.AGREE:
                agreements.setdefault(msg.target, []).append(agent)

        # Check if any proposal has everyone except its author agreeing
        for target, supporters in agreements.items():
            # Everyone except the target agrees with the target
            non_target_agents = [p.name for p in personas if p.name != target]
            if set(supporters) >= set(non_target_agents):
                return True

        return False
