"""Node implementations for The Council multi-agent discussion system."""
from importlib import import_module

__all__ = [
    "InputNode",
    "ProposalNode",
    "DebateNode",
    "ConsensusNode",
    "OutputNode",
]


def __getattr__(name: str):
    """Lazily import node classes to avoid heavy import-time dependencies."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_map = {
        "InputNode": "council.nodes.input_node",
        "ProposalNode": "council.nodes.proposal_node",
        "DebateNode": "council.nodes.debate_node",
        "ConsensusNode": "council.nodes.consensus_node",
        "OutputNode": "council.nodes.output_node",
    }
    module = import_module(module_map[name])
    return getattr(module, name)
