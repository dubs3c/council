# The Council

A multi-agent discussion system where AI agents with distinct personas analyze prompts and files, debate their perspectives, and reach consensus through structured discussion.

## How It Works

The Council orchestrates a structured debate between multiple AI agents, each with their own persona and perspective:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  InputNode  │ ──▶ │  ProposalPhase   │ ──▶ │  DebatePhase    │ ──▶ │  Consensus   │
│ (read file, │     │  (each agent     │     │  (agents review │     │  Phase       │
│  prompt,    │     │   writes initial │     │   others, may   │     │  (moderator  │
│  personas)  │     │   proposal)      │     │   revise/agree) │     │   synthesizes│
└─────────────┘     └──────────────────┘     └─────────────────┘     │   report)    │
                                                                      └──────────────┘
```

### Default Personas

1. **The Architect** - Systems Design Expert
   - Focuses on structure, scalability, and design patterns
   - Temperature: 0.8 (more creative)

2. **The Critic** - Devil's Advocate
   - Identifies risks, edge cases, and failure modes
   - Temperature: 0.5 (more focused)

3. **The Application Security Specialist** - Implementation Realist
   - Focuses on Exploitability, vulnerabilities, mitigation, risk, threat model
   - Temperature: 0.6 (balanced)

### Discussion Flow

1. **Initial Proposals**: Each agent independently analyzes the prompt/file
2. **Debate Rounds**: Agents review others' proposals and can:
   - **Revise** their own proposal
   - **Agree** with another agent
   - **Raise concerns** about unaddressed issues
3. **Early Consensus**: Discussion ends early if all agents agree
4. **Moderator Synthesis**: A neutral moderator drafts a consensus document
5. **Approval Round**: Agents approve or provide feedback
6. **Final Report**: Markdown report saved with full transcript

## Getting Started

### Installation

```bash
# Using uv (recommended)
uv sync
```

### Configure API Provider

The Council supports any OpenAI-compatible API. Set the appropriate environment variable:

```bash
# XAI
export XAI_API_KEY="your-api-key"

# Google
export GOOGLE_API_KEY="your-api-key"
```

### Basic Usage

```bash
# Simple question (uses OpenAI by default)
council --prompt "What are the pros and cons of microservices architecture?"

# Analyze a file
council --prompt "Review this architecture for potential issues" --file ./arch.md

# Watch the discussion live
council --prompt "Evaluate this API design" --file ./api.py --show-stream
```

### Full Options

```bash
council \
  --prompt "Review this architecture" \
  --file ./arch.md \
  --personas ./my_personas.yaml \
  --max-turns 5 \
  --show-stream \
  --output-dir ./reports
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--prompt` | `-p` | Required | The question for the council |
| `--file` | `-f` | None | File to analyze |
| `--personas` | | `config/default_personas.yaml` | Custom personas file |
| `--max-turns` | `-t` | 3 | Maximum debate rounds |
| `--show-stream` | `-s` | False | Print discussion live |
| `--output-dir` | `-o` | `.` | Report output directory |

## LLM Provider Configuration

Each agent can use a different LLM provider. Configure providers in your personas YAML file:

### Default Provider (applies to all agents)

```yaml
default_provider:
  api_key: "$GOOGLE_API_KEY"
  base_url: "https://generativelanguage.googleapis.com/v1beta/openai/"
  model: "gemini-3-flash-preview"

personas:
  - name: "The Architect"
    # ... uses default_provider
```

### Per-Agent Providers (mix different models)

```yaml
default_provider:
  api_key: "$OPENAI_API_KEY"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

personas:
  - name: "The Architect"
    role: "Systems Design Expert"
    focus: "Structure, scalability, patterns"
    temperature: 0.8
    provider:
      api_key: "$OPENAI_API_KEY"
      base_url: "https://api.openai.com/v1"
      model: "gpt-4o"  # Uses GPT-4o
    style: |
      You analyze systems holistically...

  - name: "The Critic"
    role: "Devil's Advocate"
    focus: "Risks, edge cases, security"
    temperature: 0.5
    provider:
      api_key: "$ANTHROPIC_API_KEY"
      base_url: "https://api.anthropic.com/v1"
      model: "claude-3-opus-20240229"  # Uses Claude
    style: |
      You identify what could go wrong...

  - name: "The Pragmatist"
    role: "Implementation Realist"
    focus: "Feasibility, complexity, trade-offs"
    temperature: 0.6
    provider:
      api_key: "ollama"
      base_url: "http://localhost:11434/v1"
      model: "llama3"  # Uses local Ollama
    style: |
      You ground discussions in reality...
```

### Supported Providers

Any OpenAI-compatible API works. Common providers:

| Provider | Base URL | Notes |
|----------|----------|-------|
| XAI | `https://api.x.ai/v1` | Default |
| Google | `https://generativelanguage.googleapis.com/v1beta/openai/` | Default |
| OpenAI | `https://api.openai.com/v1` |  |
| Anthropic | `https://api.anthropic.com/v1` | |
| Together AI | `https://api.together.xyz/v1` | |
| Groq | `https://api.groq.com/openai/v1` | Fast inference |
| Ollama | `http://localhost:11434/v1` | Local models |
| Azure OpenAI | `https://{resource}.openai.azure.com/...` |  |
| OpenRouter | `https://openrouter.ai/api/v1` | Multi-provider |

## Custom Personas

Create a YAML file with your own personas:

```yaml
default_provider:
  api_key: "$OPENAI_API_KEY"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"

personas:
  - name: "The Security Expert"
    role: "Security Analyst"
    focus: "Vulnerabilities, attack vectors, data protection"
    temperature: 0.4
    style: |
      You analyze everything through a security lens. You look for
      potential vulnerabilities, data exposure risks, and authentication
      weaknesses. You ask "How could this be exploited?"

  - name: "The UX Advocate"
    role: "User Experience Designer"
    focus: "Usability, accessibility, user workflows"
    temperature: 0.7
    style: |
      You focus on the human side. How will users interact with this?
      What friction points exist? Is it accessible to all users?
```

Then use it:

```bash
council --prompt "Review this login flow" --file ./auth.py --personas ./security_ux.yaml
```

## Output

The Council generates a Markdown report with:

- **Consensus Summary**: The agreed-upon conclusion
- **Strengths**: Points all agents agreed on
- **Concerns & Resolutions**: Issues raised and how they were addressed
- **Recommendations**: Prioritized action items (high/medium/low)
- **Dissenting Views**: Any unreconciled positions
- **Full Transcript**: Complete discussion history (collapsible)

Reports are saved with unique timestamps: `council_report_20260102_143052.md`

## Example Session

```bash
$ council --prompt "Should we use a monorepo or polyrepo for our microservices?" --show-stream

============================================================
THE COUNCIL
============================================================

Prompt: Should we use a monorepo or polyrepo for our microservices?...
Agents: The Architect, The Critic, The Pragmatist
Max turns: 3
============================================================

============================================================
INITIAL PROPOSAL: The Architect
============================================================
### The Architect's Proposal

**Summary:** A monorepo offers better code sharing and atomic changes...
...

============================================================
DEBATE - Turn 1
============================================================
**The Critic** (Turn 1) - *concern*
> What about build times at scale? Large monorepos can have...
...

*** CONSENSUS REACHED at Turn 2 ***

============================================================
COUNCIL SESSION COMPLETE
============================================================

Both approaches have merit; the choice depends on team size and tooling maturity.

Top Recommendations:
  1. Start with monorepo if team is small (<20 developers)
  2. Invest in build caching and CI optimization early
  3. Define clear module boundaries regardless of repo structure

Full report saved to: ./council_report_20260102_143052.md
============================================================
```

See full example [here](docs/council_report_example.md).

## Project Structure

```
/src
├── main.py                 # CLI entry point
├── flow.py                 # Flow orchestration
├── models.py               # Data structures
├── utils.py                # LLM wrapper (OpenAI-compatible)
├── config/
│   └── default_personas.yaml
├── nodes/
│   ├── input_node.py       # File/prompt loading
│   ├── proposal_node.py    # Initial proposals
│   ├── debate_node.py      # Debate rounds
│   ├── consensus_node.py   # Moderator synthesis
│   └── output_node.py      # Report generation
└── pyproject.toml          # Project dependencies
```

## Requirements

- Python 3.12+
- API key for your chosen provider(s)
- Dependencies: `pocketflow`, `openai`, `pyyaml`

## License
MIT
