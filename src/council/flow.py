"""Flow orchestration for The Council multi-agent discussion system."""

from pocketflow import Flow

from council.nodes.agent_summary_node import AgentSummaryNode
from council.nodes.consensus_node import ConsensusNode
from council.nodes.debate_node import DebateNode
from council.nodes.input_node import InputNode
from council.nodes.output_node import OutputNode
from council.nodes.proposal_node import ProposalNode


def create_council_flow() -> Flow:
    """Create and wire the council discussion flow.

    Flow structure:

    InputNode
        │
        ▼
    ProposalNode (BatchNode - parallel initial proposals)
        │
        ▼
    ┌─────────────────────────────────────┐
    │ DebateNode                          │◀─────┐
    │ (agents review/revise/agree)        │      │
    └─────────────────────────────────────┘      │
        │                                        │
        ├── "continue" ──────────────────────────┘
        │
        ├── "consensus_ready" ──┐
        │                       │
        ├── "max_turns" ────────┤
        │                       │
        ▼                       ▼
    AgentSummaryNode ◀──────────┘
        │
        ▼
    ConsensusNode
        │
        ▼
    OutputNode
        │
        ▼
      END

    Returns:
        Configured Flow ready to run
    """
    # Create nodes
    input_node = InputNode()
    proposal_node = ProposalNode(max_retries=2, wait=5)
    debate_node = DebateNode(max_retries=2, wait=5)
    agent_summary_node = AgentSummaryNode(max_retries=2, wait=5)
    consensus_node = ConsensusNode(max_retries=2, wait=5)
    output_node = OutputNode()

    # Wire the flow
    # InputNode -> ProposalNode
    input_node - "default" >> proposal_node
    input_node - "error" >> output_node  # Skip to output on input error

    # ProposalNode -> DebateNode
    proposal_node - "default" >> debate_node

    # DebateNode transitions
    debate_node - "continue" >> debate_node  # Loop back for more debate
    debate_node - "consensus_ready" >> agent_summary_node  # Early consensus
    (
        debate_node - "max_turns" >> agent_summary_node
    )  # Force consensus after max turns

    # AgentSummaryNode -> ConsensusNode
    agent_summary_node - "default" >> consensus_node

    # ConsensusNode -> OutputNode
    consensus_node - "default" >> output_node

    # Create and return the flow
    flow = Flow(start=input_node)

    return flow


def run_council(
    prompt: str,
    file_path: str = None,
    personas_path: str = None,
    max_turns: int = 3,
    show_stream: bool = False,
    output_dir: str = ".",
) -> dict:
    """Run a council discussion session.

    Args:
        prompt: The question or request to discuss
        file_path: Optional path to a file to analyze
        personas_path: Optional path to custom personas YAML
        max_turns: Maximum debate rounds (default 3)
        show_stream: Whether to print discussion as it happens
        output_dir: Directory to save the report

    Returns:
        Dictionary with results including:
        - report_filepath: Path to saved report
        - report_content: Full report as markdown string
        - final_report: ConsensusReport object
    """
    # Initialize shared state with CLI args
    shared = {
        "prompt": prompt,
        "file_path": file_path,
        "personas_path": personas_path,
        "max_turns": max_turns,
        "show_stream": show_stream,
        "output_dir": output_dir,
    }

    # Create and run flow
    flow = create_council_flow()
    flow.run(shared)

    # Return results
    return {
        "report_filepath": shared.get("report_filepath"),
        "report_content": shared.get("report_content"),
        "final_report": shared.get("final_report"),
        "proposals": shared.get("proposals", []),
        "debate_messages": shared.get("debate_messages", []),
    }


if __name__ == "__main__":
    # Quick test
    result = run_council(
        prompt="What are the pros and cons of microservices architecture?",
        show_stream=True,
        max_turns=2,
    )
    print(f"\nReport saved to: {result['report_filepath']}")
