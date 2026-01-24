"""Consensus node for moderator synthesis."""

from pocketflow import Node

from council.console import (
    print_consensus_feedback,
    print_consensus_start,
    print_consensus_status,
    print_error,
    print_final_consensus,
)
from council.models import (
    ConcernResolution,
    ConsensusPoint,
    ConsensusReport,
    DebateMessage,
    DissentingView,
    Persona,
    Proposal,
    ProviderConfig,
    Recommendation,
)
from council.utils import call_llm, parse_json_response


class ConsensusNode(Node):
    """Node for moderator to synthesize consensus.

    The moderator is a neutral system role that:
    1. Reviews all proposals and debate
    2. Drafts a consensus document
    3. Gets approval/feedback from agents
    4. Finalizes the report
    """

    def prep(self, shared):
        """Gather all discussion context."""
        # Use first persona's provider for moderator (could be configured separately)
        personas = shared["personas"]
        moderator_provider = (
            personas[0].provider if personas else ProviderConfig()
        )

        return {
            "prompt": shared["prompt"],
            "file_path": shared.get("file_path"),
            "proposals": shared["proposals"],
            "debate_messages": shared.get("debate_messages", []),
            "personas": personas,
            "show_stream": shared["config"]["show_stream"],
            "moderator_provider": moderator_provider,
        }

    def exec(self, prep_res):
        """Generate consensus document."""
        prompt = prep_res["prompt"]
        proposals = prep_res["proposals"]
        debate_messages = prep_res["debate_messages"]
        personas = prep_res["personas"]
        show_stream = prep_res["show_stream"]
        moderator_provider = prep_res["moderator_provider"]

        # Format discussion for moderator
        discussion = self._format_discussion(proposals, debate_messages)

        if show_stream:
            print_consensus_start()

        # Step 1: Generate initial consensus draft
        draft = self._generate_draft(
            prompt, discussion, personas, moderator_provider
        )

        if show_stream:
            print_consensus_status(
                "Draft consensus generated. Seeking approval..."
            )

        # Step 2: Get agent feedback
        feedback = self._get_agent_feedback(draft, personas, prompt)

        # Step 3: Finalize based on feedback
        final_report = self._finalize_report(
            draft, feedback, prompt, show_stream, moderator_provider
        )

        return {
            "report": final_report,
            "show_stream": show_stream,
        }

    def _format_discussion(
        self, proposals: list[Proposal], debate_messages: list[DebateMessage]
    ) -> str:
        """Format full discussion for moderator review."""
        lines = ["## Initial Proposals\n"]

        for proposal in proposals:
            lines.append(proposal.to_markdown())
            lines.append("")

        if debate_messages:
            lines.append("\n## Debate\n")
            current_turn = 0
            for msg in debate_messages:
                if msg.turn != current_turn:
                    current_turn = msg.turn
                    lines.append(f"\n### Turn {current_turn}\n")
                lines.append(msg.to_markdown())
                lines.append("")

        return "\n".join(lines)

    def _generate_draft(
        self,
        prompt: str,
        discussion: str,
        personas: list[Persona],
        moderator_provider: ProviderConfig,
    ) -> ConsensusReport:
        """Generate initial consensus draft."""
        agent_names = [p.name for p in personas]

        llm_prompt = f"""You are a neutral moderator synthesizing a council discussion.

## Original Question

{prompt}

## Discussion

{discussion}

## Your Task

Synthesize the discussion into a consensus document. Identify:
1. Points everyone agrees on (strengths)
2. Concerns raised and how they were resolved
3. Prioritized recommendations
4. Any views that couldn't be reconciled

Return your response as JSON with this structure:

{{
  "summary": "A clear 2-3 sentence summary of the consensus reached",
  "strengths": [
    {{"point": "Something the council agrees is positive or important", "supporters": ["Agent Name 1", "Agent Name 2"]}}
  ],
  "concerns": [
    {{"concern": "A concern that was raised", "raised_by": "Agent Name", "resolution": "How it was addressed or resolved"}}
  ],
  "recommendations": [
    {{"priority": "high", "action": "Specific actionable recommendation", "rationale": "Why this matters"}}
  ],
  "dissenting_views": [
    {{"agent": "Agent Name", "position": "Their unreconciled position"}}
  ]
}}

Notes:
- priority: "high", "medium", or "low"
- dissenting_views: Only include if genuine disagreement remains

Be fair and balanced. Accurately represent each agent's views.
Available agents: {", ".join(agent_names)}"""

        response = call_llm(
            llm_prompt, temperature=0.3, provider=moderator_provider
        )

        # Parse JSON
        parsed = parse_json_response(response)

        # Build ConsensusReport
        strengths = []
        for s in parsed.get("strengths", []):
            strengths.append(
                ConsensusPoint(
                    point=s["point"], supporters=s.get("supporters", [])
                )
            )

        concerns = []
        for c in parsed.get("concerns", []):
            concerns.append(
                ConcernResolution(
                    concern=c["concern"],
                    raised_by=c["raised_by"],
                    resolution=c["resolution"],
                )
            )

        recommendations = []
        for r in parsed.get("recommendations", []):
            recommendations.append(
                Recommendation(
                    priority=r.get("priority", "medium"),
                    action=r["action"],
                    rationale=r["rationale"],
                )
            )

        dissenting = []
        for d in parsed.get("dissenting_views", []):
            dissenting.append(
                DissentingView(agent=d["agent"], position=d["position"])
            )

        return ConsensusReport(
            summary=parsed.get("summary", "").strip(),
            strengths=strengths,
            concerns=concerns,
            recommendations=recommendations,
            dissenting_views=dissenting,
        )

    def _get_agent_feedback(
        self, draft: ConsensusReport, personas: list[Persona], prompt: str
    ) -> list[dict]:
        """Get each agent's feedback on the draft."""
        feedback = []
        draft_md = draft.to_markdown()

        for persona in personas:
            llm_prompt = f"""{persona.to_prompt()}

## Original Question

{prompt}

## Draft Consensus Document

{draft_md}

## Your Task

Review this consensus document. Does it fairly represent your views and the discussion?

Return your response as JSON: {{"approval": true, "feedback": "Your feedback here"}}"""

            response = call_llm(
                llm_prompt,
                temperature=persona.temperature,
                provider=persona.provider,
            )

            try:
                parsed = parse_json_response(response)
                feedback.append(
                    {
                        "agent": persona.name,
                        "approved": parsed.get("approval", False),
                        "feedback": parsed.get("feedback", "").strip(),
                    }
                )
            except Exception as e:
                # Assume approval on parse failure
                feedback.append(
                    {
                        "agent": persona.name,
                        "approved": True,
                        "feedback": f"[Parse error: {e}]",
                    }
                )

        return feedback

    def _finalize_report(
        self,
        draft: ConsensusReport,
        feedback: list[dict],
        prompt: str,
        show_stream: bool,
        moderator_provider: ProviderConfig,
    ) -> ConsensusReport:
        """Finalize report based on feedback."""
        # Check if everyone approved
        all_approved = all(f["approved"] for f in feedback)

        if all_approved:
            if show_stream:
                print_consensus_status("All agents approved the consensus!")
            return draft

        # Need to revise - incorporate feedback
        if show_stream:
            print_consensus_status("Some agents had feedback. Revising...")
            print_consensus_feedback(feedback)

        # Format feedback for revision
        feedback_text = "\n".join(
            [
                f"**{f['agent']}** ({'Approved' if f['approved'] else 'Changes requested'}): {f['feedback']}"
                for f in feedback
            ]
        )

        llm_prompt = f"""You are a neutral moderator revising a consensus document based on agent feedback.

## Original Question

{prompt}

## Current Draft

{draft.to_markdown()}

## Agent Feedback

{feedback_text}

## Your Task

Revise the consensus document to address the feedback while maintaining balance.

Return your response as JSON with the same structure:

{{"summary": "Updated summary",
  "strengths": [{{"point": "...", "supporters": ["..."]}}],
  "concerns": [{{"concern": "...", "raised_by": "...", "resolution": "..."}}],
  "recommendations": [{{"priority": "high", "action": "...", "rationale": "..."}}],
  "dissenting_views": [{{"agent": "...", "position": "..."}}]
}}"""

        response = call_llm(
            llm_prompt, temperature=0.3, provider=moderator_provider
        )

        try:
            parsed = parse_json_response(response)

            # Rebuild report
            strengths = [
                ConsensusPoint(
                    point=s["point"], supporters=s.get("supporters", [])
                )
                for s in parsed.get("strengths", [])
            ]
            concerns = [
                ConcernResolution(
                    concern=c["concern"],
                    raised_by=c["raised_by"],
                    resolution=c["resolution"],
                )
                for c in parsed.get("concerns", [])
            ]
            recommendations = [
                Recommendation(
                    priority=r.get("priority", "medium"),
                    action=r["action"],
                    rationale=r["rationale"],
                )
                for r in parsed.get("recommendations", [])
            ]
            dissenting = [
                DissentingView(agent=d["agent"], position=d["position"])
                for d in parsed.get("dissenting_views", [])
            ]

            return ConsensusReport(
                summary=parsed.get("summary", "").strip(),
                strengths=strengths,
                concerns=concerns,
                recommendations=recommendations,
                dissenting_views=dissenting,
            )
        except Exception:
            # Return original draft on failure
            return draft

    def exec_fallback(self, prep_res, exc):
        """Handle errors gracefully."""
        print_error(f"During consensus: {exc}")
        return {
            "report": ConsensusReport(
                summary="[Error occurred during consensus generation]",
                strengths=[],
                concerns=[],
                recommendations=[],
                dissenting_views=[],
            ),
            "show_stream": prep_res["show_stream"],
        }

    def post(self, shared, prep_res, exec_res):
        """Store final report."""
        shared["final_report"] = exec_res["report"]

        if exec_res["show_stream"]:
            print_final_consensus(exec_res["report"].to_markdown())

        return "default"
