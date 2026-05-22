"""Output node for generating and saving reports."""

import os
from datetime import datetime

from pocketflow import Node

from council.console import print_error, print_session_complete
from council.models import AgentDiscussionSummary, DebateMessage, Proposal


class OutputNode(Node):
    """Node for generating and saving the final report.

    Creates a markdown report with:
    - Metadata (timestamp, prompt, file)
    - Consensus summary and recommendations
    - Full discussion transcript (optional)
    """

    def prep(self, shared):
        """Gather all data for the report."""
        return {
            "prompt": shared["prompt"],
            "file_path": shared.get("file_path"),
            "personas": shared["personas"],
            "proposals": shared["proposals"],
            "debate_messages": shared.get("debate_messages", []),
            "agent_summaries": shared.get("agent_summaries"),
            "compacted_context": shared.get("compacted_context"),
            "final_report": shared.get("final_report"),
            "output_dir": shared["config"]["output_dir"],
            "show_stream": shared["config"]["show_stream"],
        }

    def exec(self, prep_res):
        """Generate the full markdown report."""
        timestamp = datetime.now()

        # Build the report
        lines = [
            "# Council Report",
            "",
            f"**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"**Prompt:** {prep_res['prompt']}",
            "",
        ]

        if prep_res["file_path"]:
            lines.append(f"**File Analyzed:** `{prep_res['file_path']}`")
            lines.append("")

        lines.append(
            f"**Council Members:** {', '.join(p.name for p in prep_res['personas'])}"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add consensus report
        if prep_res["final_report"]:
            lines.append(prep_res["final_report"].to_markdown())
        else:
            lines.append("## Summary")
            lines.append("")
            lines.append("*No consensus was reached.*")

        lines.append("")
        lines.append("---")
        lines.append("")

        if prep_res["agent_summaries"]:
            lines.append(
                self._format_agent_summaries(prep_res["agent_summaries"])
            )
            lines.append("")
            lines.append("---")
            lines.append("")

        if prep_res["compacted_context"] is not None:
            lines.append("## Context Compaction Note")
            lines.append("")
            lines.append(
                "Compacted context was used during prompt construction. "
                "The full discussion transcript below remains complete."
            )
            lines.append("")
            lines.append("---")
            lines.append("")

        # Add discussion transcript in collapsible section
        lines.append("<details>")
        lines.append(
            "<summary><strong>Full Discussion Transcript</strong></summary>"
        )
        lines.append("")
        lines.append(
            self._format_transcript(
                prep_res["proposals"], prep_res["debate_messages"]
            )
        )
        lines.append("")
        lines.append("</details>")
        lines.append("")

        report_content = "\n".join(lines)

        # Generate unique filename
        filename = f"council_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(prep_res["output_dir"], filename)

        return {
            "content": report_content,
            "filepath": filepath,
            "timestamp": timestamp,
        }

    def _format_transcript(
        self, proposals: list[Proposal], debate_messages: list[DebateMessage]
    ) -> str:
        """Format the full discussion transcript."""
        lines = ["### Initial Proposals", ""]

        for proposal in proposals:
            if proposal.turn == 0:
                lines.append(proposal.to_markdown())
                lines.append("")

        if debate_messages:
            lines.append("### Debate Rounds")
            lines.append("")

            current_turn = 0
            for msg in debate_messages:
                if msg.turn != current_turn:
                    current_turn = msg.turn
                    lines.append(f"#### Turn {current_turn}")
                    lines.append("")

                lines.append(msg.to_markdown())
                lines.append("")

        return "\n".join(lines)

    def _format_agent_summaries(
        self, agent_summaries: list[AgentDiscussionSummary]
    ) -> str:
        """Format independent agent summaries without blending viewpoints."""
        lines = ["## Independent Agent Summaries", ""]

        for summary in agent_summaries:
            lines.append(f"### {summary.agent}")
            lines.append("")
            lines.append(f"**Initial Position:** {summary.initial_position}")
            lines.append(f"**Current Position:** {summary.current_position}")
            lines.append(f"**Final Stance:** {summary.final_stance}")
            lines.append("")
            lines.append("**Revision History:**")
            lines.extend(self._format_list(summary.revision_history))
            lines.append("")
            lines.append("**Concerns Raised:**")
            lines.extend(self._format_list(summary.concerns_raised))
            lines.append("")
            lines.append("**Agreements:**")
            lines.extend(self._format_list(summary.agreements))
            lines.append("")
            lines.append("**Unresolved Concerns:**")
            lines.extend(self._format_list(summary.unresolved_concerns))
            lines.append("")

        return "\n".join(lines).rstrip()

    def _format_list(self, items: list[str]) -> list[str]:
        """Format a simple markdown list with an explicit empty state."""
        if not items:
            return ["- [None]"]
        return [f"- {item}" for item in items]

    def exec_fallback(self, prep_res, exc):
        """Handle errors gracefully."""
        print_error(f"Generating report: {exc}")

        timestamp = datetime.now()
        filename = (
            f"council_report_{timestamp.strftime('%Y%m%d_%H%M%S')}_error.md"
        )
        filepath = os.path.join(prep_res["output_dir"], filename)

        return {
            "content": f"# Council Report\n\n**Error:** {exc}",
            "filepath": filepath,
            "timestamp": timestamp,
        }

    def post(self, shared, prep_res, exec_res):
        """Save report and print summary."""
        # Save to file
        output_dir = prep_res["output_dir"]
        os.makedirs(output_dir, exist_ok=True)

        with open(exec_res["filepath"], "w") as f:
            f.write(exec_res["content"])

        # Print final output
        final_report = prep_res["final_report"]
        print_session_complete(
            summary=final_report.summary if final_report else None,
            recommendations=final_report.recommendations
            if final_report
            else None,
            filepath=exec_res["filepath"],
        )

        # Store in shared for testing/programmatic access
        shared["report_filepath"] = exec_res["filepath"]
        shared["report_content"] = exec_res["content"]

        return "end"
