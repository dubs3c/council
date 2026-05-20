"""Debate node for agent discussion and revision."""

from pocketflow import BatchNode

from council.console import (
    print_debate_message,
    print_debate_turn,
    print_special_event,
    print_warning,
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

        # Format all current proposals for context
        proposals_context = self._format_proposals(proposals, debate_messages)

        # Create input for each persona
        inputs = []
        for persona in personas:
            inputs.append(
                {
                    "persona": persona,
                    "proposals_context": proposals_context,
                    "current_turn": current_turn,
                    "prompt": shared["prompt"],
                    "show_stream": shared["config"]["show_stream"],
                    "own_proposal": self._get_latest_proposal(
                        persona.name, proposals, debate_messages
                    ),
                }
            )

        return inputs

    def _format_proposals(
        self, proposals: list[Proposal], debate_messages: list[DebateMessage]
    ) -> str:
        """Format current proposals and debate history for context."""
        lines = ["## Current Proposals\n"]

        # Get latest proposal for each agent
        latest = {}
        for p in proposals:
            latest[p.agent] = p

        for msg in debate_messages:
            if msg.action == DebateAction.REVISE and msg.proposal_revision:
                prior = latest.get(msg.agent)
                if prior:
                    latest[msg.agent] = self._apply_revision(
                        prior, msg.proposal_revision
                    )

        for agent, proposal in latest.items():
            lines.append(proposal.to_markdown())
            lines.append("")

        # Add debate history if any
        if debate_messages:
            lines.append("\n## Debate History\n")
            for msg in debate_messages:
                lines.append(msg.to_markdown())
                lines.append("")

        return "\n".join(lines)

    def _get_latest_proposal(
        self,
        agent_name: str,
        proposals: list[Proposal],
        debate_messages: list[DebateMessage],
    ) -> Proposal | None:
        """Get the most recent proposal for an agent."""
        latest = None
        for p in proposals:
            if p.agent == agent_name:
                latest = p

        for msg in debate_messages:
            if (
                msg.agent == agent_name
                and msg.action == DebateAction.REVISE
                and msg.proposal_revision
            ):
                if latest:
                    latest = self._apply_revision(latest, msg.proposal_revision)

        return latest

    def _apply_revision(
        self, base: Proposal, revision: ProposalRevision
    ) -> Proposal:
        """Apply a partial proposal revision to a base proposal."""
        return Proposal(
            agent=base.agent,
            summary=revision.summary if revision.summary is not None else base.summary,
            analysis=revision.analysis if revision.analysis is not None else base.analysis,
            recommendations=(
                revision.recommendations
                if revision.recommendations is not None
                else base.recommendations
            ),
            turn=base.turn,
        )

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
        latest_actions = {}
        for msg in debate_messages:
            latest_actions[msg.agent] = msg

        # Count agreements
        agreements = {}
        for agent, msg in latest_actions.items():
            if msg.action == DebateAction.AGREE:
                target = msg.target
                if target not in agreements:
                    agreements[target] = []
                agreements[target].append(agent)

        # Check if any proposal has everyone except its author agreeing
        for target, supporters in agreements.items():
            # Everyone except the target agrees with the target
            non_target_agents = [p.name for p in personas if p.name != target]
            if set(supporters) >= set(non_target_agents):
                return True

        return False
