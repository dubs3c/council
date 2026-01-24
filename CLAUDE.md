# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**The Council** is a multi-agent AI discussion system where agents with distinct personas analyze questions/files, debate their perspectives, and reach consensus through structured discussion. Built using the PocketFlow workflow orchestration library.

## Development Commands

### Setup
```bash
# Install dependencies (recommended)
uv sync

# Or using pip
pip install -e .
```

### Running The Council
```bash
# Basic usage with default personas (uses Python from .venv)
.venv/bin/python main.py --prompt "Your question here"

# With file analysis
.venv/bin/python main.py --prompt "Review this" --file ./path/to/file

# With live streaming and custom settings
.venv/bin/python main.py --prompt "Question" --file ./file.py \
  --show-stream --max-turns 5 --output-dir ./reports

# With custom personas
.venv/bin/python main.py --prompt "Question" \
  --personas ./config/custom_personas.yaml
```

### Testing
```bash
# Run all tests
.venv/bin/python -m unittest discover tests

# Run specific test
.venv/bin/python -m unittest tests.test_utils
```

### Linting
```bash
# Check code style (ruff is configured)
.venv/bin/python -m ruff check .

# Auto-fix issues
.venv/bin/python -m ruff check --fix .
```

## Architecture

### Flow Orchestration (PocketFlow)

The Council uses PocketFlow nodes in a structured pipeline:

```
InputNode → ProposalNode → DebateNode ⟲ → ConsensusNode → OutputNode
                              ↑____________|
```

**Key Flow Points:**
- **InputNode**: Loads prompt, file content, and personas from YAML
- **ProposalNode (BatchNode)**: Runs agents in parallel to generate initial proposals
- **DebateNode (BatchNode)**: Iterative debate rounds where agents can REVISE, AGREE, or raise CONCERN
  - Loops back to itself with "continue" edge
  - Exits via "consensus_ready" (early agreement) or "max_turns" (forced consensus)
- **ConsensusNode**: Moderator synthesizes final report with approval round
- **OutputNode**: Generates markdown report with transcript

**Shared State Pattern**: All nodes read/write to a shared dictionary that flows through the pipeline. Key shared fields:
- `prompt`, `file_content`, `file_path`: Input context
- `personas`: List of Persona objects with provider configs
- `proposals`: List of initial Proposal objects
- `debate_messages`: List of DebateMessage objects tracking revisions/agreements
- `current_turn`: Debate round counter
- `final_report`: ConsensusReport object
- `config`: Dict with `max_turns`, `show_stream`, `output_dir`

### Multi-Provider LLM Support

Each agent can use a different LLM provider/model via `ProviderConfig`:
- Supports any OpenAI-compatible API (OpenAI, Anthropic via proxy, Groq, Together AI, Ollama, Azure)
- Configuration in `config/default_personas.yaml` with `default_provider` and per-persona `provider` overrides
- Environment variable references: `api_key: "$OPENAI_API_KEY"` resolved at runtime via `ProviderConfig.get_api_key()`
- See `models.py:ProviderConfig` and `utils.py:call_llm()`

### Data Models (models.py)

**Core Enums:**
- `DebateAction`: REVISE | AGREE | CONCERN
- `ApprovalStatus`: APPROVE | FEEDBACK

**Key Dataclasses:**
- `Persona`: Agent personality with name, role, focus, style, temperature, and `ProviderConfig`
- `Proposal`: Agent's analysis with summary, analysis points (point + reasoning), and recommendations
- `DebateMessage`: Turn action (revise/agree/concern) with reasoning, optional target/concern/updated_proposal
- `ConsensusReport`: Final report with summary, strengths (ConsensusPoint), concerns (ConcernResolution), recommendations (prioritized), and dissenting views
- `DiscussionState`: Helper class with consensus checking logic (currently not actively used but tracks state structure)

### Node Execution Pattern

All nodes follow PocketFlow's lifecycle:
1. **prep(shared)**: Extract inputs from shared state, return prep result
2. **exec(prep_res)**: Execute node logic, return exec result
3. **exec_fallback(prep_res, exc)**: Handle errors gracefully (important for LLM failures)
4. **post(shared, prep_res, exec_res)**: Update shared state, return edge name for routing

**BatchNode Pattern** (ProposalNode, DebateNode):
- `prep()` returns a list of inputs (one per agent)
- `exec()` runs in parallel for each input
- `post()` receives list of exec results

### Consensus Detection

Consensus is reached when all agents except one agree with that agent's proposal:
- Tracked via `DebateAction.AGREE` messages with `target` field
- Checked in `DebateNode.post()` via `_check_consensus()`
- Early exit from debate loop when detected

### LLM Interaction Pattern

All agent interactions use structured YAML responses:
1. Persona prompt + task context sent to LLM
2. LLM returns YAML in markdown code block
3. `parse_yaml_response()` extracts and parses YAML
4. Validates required fields and constructs dataclass objects

**Error Handling**: All nodes have `exec_fallback()` to gracefully handle LLM failures (API errors, malformed responses). Fallback responses keep the flow moving rather than crashing.

## Important Implementation Details

### Persona Configuration

Default personas in `config/default_personas.yaml`:
1. **The Architect** - Systems design, scalability (temp: 0.8)
2. **The Critic** - Risks, edge cases, security (temp: 0.5)
3. **The Pragmatist** - Feasibility, trade-offs (temp: 0.6)

Custom personas can be provided via `--personas` flag. Required fields per persona:
- `name`, `role`, `focus`, `style` (multiline string)
- Optional: `temperature`, `provider` (overrides default_provider)

### File Size Limits

`input_node.py` enforces:
- Warning at 1 MB
- Hard limit at 10 MB (raises ValueError)

### Output Format

Generated reports include:
- Consensus summary and strengths
- Concerns & resolutions table
- Prioritized recommendations (high/medium/low)
- Dissenting views (if any)
- Full discussion transcript (collapsible in markdown)

Reports saved as `council_report_YYYYMMDD_HHMMSS.md` in output directory.

### Console Output

`console.py` uses Rich library for styled terminal output:
- `print_council_header()`: Session info
- `print_proposal()`: Initial proposals
- `print_debate_turn()`: Turn separator
- `print_debate_message()`: Agent debate actions
- `print_special_event()`: Consensus/max turns reached
- Only active when `--show-stream` flag is set

## Debugging Tips

- Enable `--show-stream` to watch the full discussion unfold in real-time
- Check `shared` state at each node boundary (add print statements in `post()` methods)
- LLM parsing failures: inspect raw responses before `parse_yaml_response()` call
- Consensus not reached: review `DebateNode._check_consensus()` logic and agent agreement chains
- Provider errors: verify API keys are set and `base_url` is correct for the provider
