# Agent Guidelines for The Council

This document provides essential information for AI coding agents working in this repository.

## Project Overview

The Council is a multi-agent discussion system where AI agents with distinct personas analyze prompts and files, debate their perspectives, and reach consensus through structured discussion. Built on the PocketFlow framework.

**Stack:** Python 3.10+, PocketFlow framework, Anthropic Claude API, YAML parsing

## Build, Test, and Run Commands

### Installation
```bash
pip install -r requirements.txt
```

### Set API Key
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### Run the Application
```bash
# Basic usage
python main.py --prompt "Your question here"

# With file analysis
python main.py --prompt "Review this" --file ./code.py

# Full options
python main.py --prompt "..." --file ./code.py --max-turns 3 --show-stream

# Test LLM utility
python utils.py
```

### Linting
**CRITICAL:** Run `ruff check` after EVERY file creation or modification.

```bash
# Check all files
ruff check .

# Fix auto-fixable issues
ruff check . --fix

# Check specific file
ruff check path/to/file.py
```

**Agent Workflow:**
1. Create or modify Python file(s)
2. Run `ruff check .` immediately
3. Fix any issues reported
4. Verify with `ruff check .` again

### Testing
**Status:** No test framework currently configured. To add tests:
- Use `pytest` as the testing framework
- Place tests in a `tests/` directory
- Run single test: `pytest tests/test_filename.py::test_function_name -v`

## Project Structure

```
/
├── main.py                 # CLI entry point
├── flow.py                 # Flow orchestration
├── models.py               # Data structures (Persona, Proposal, etc.)
├── utils.py                # LLM wrapper (call_llm)
├── config/
│   └── default_personas.yaml
├── nodes/
│   ├── __init__.py
│   ├── input_node.py       # File/prompt loading, validation
│   ├── proposal_node.py    # Initial proposals (BatchNode)
│   ├── debate_node.py      # Debate rounds
│   ├── consensus_node.py   # Moderator synthesis
│   └── output_node.py      # Report generation
└── requirements.txt
```

## Code Style Guidelines

### Import Organization
```python
# 1. Standard library
import argparse
import os
from datetime import datetime
from typing import List, Optional

# 2. Third-party
from anthropic import Anthropic
import yaml

# 3. PocketFlow framework
from pocketflow import BatchNode, Flow, Node

# 4. Local imports
from models import Persona, Proposal
from utils import call_llm
```

### PocketFlow Node Pattern

**Always use the 3-step pattern: prep → exec → post**

```python
class MyNode(Node):
    def prep(self, shared):
        """Read from shared store. Return data for exec()."""
        return shared.get("key")

    def exec(self, prep_res):
        """Pure computation. NO shared store access. Must be idempotent."""
        return call_llm(prompt, temperature=0.7)

    def exec_fallback(self, prep_res, exc):
        """Handle errors after all retries. Return fallback value."""
        return None

    def post(self, shared, prep_res, exec_res):
        """Write to shared store. Return action string for flow control."""
        shared["result"] = exec_res
        return "default"  # or "continue", "consensus_ready", etc.
```

### Data Models (models.py)

Use dataclasses for structured data:
```python
@dataclass
class Persona:
    name: str
    role: str
    focus: str
    style: str
    temperature: float = 0.7
```

### Structured Output (YAML over JSON)

LLMs handle YAML better than JSON (escaping issues). Always use this pattern:

```python
prompt = f"""
Return strictly in this YAML format:
```yaml
field: value
list:
  - item1
  - item2
```"""

response = call_llm(prompt, temperature=persona.temperature)
yaml_part = response.split("```yaml")[1].split("```")[0].strip()
parsed = yaml.safe_load(yaml_part)
```

### Flow Transitions

Use action strings to control flow:
```python
# In post() method
return "default"          # Continue to next node
return "continue"         # Loop back (e.g., more debate)
return "consensus_ready"  # Skip to consensus
return "error"            # Handle error path
```

Wire nodes in flow.py:
```python
node_a - "default" >> node_b
node_a - "error" >> error_handler
debate_node - "continue" >> debate_node  # Self-loop
```

### Error Handling

Let PocketFlow handle retries:
```python
my_node = MyNode(max_retries=3, wait=5)  # 3 attempts, 5 sec between

def exec(self, prep_res):
    result = call_llm(prompt)  # May fail - auto-retries
    if not valid(result):
        raise ValueError("Invalid")  # Triggers retry
    return result

def exec_fallback(self, prep_res, exc):
    print(f"Failed: {exc}")
    return None  # Graceful degradation
```

### Naming Conventions

- **Classes**: PascalCase (`ProposalNode`, `ConsensusReport`)
- **Functions/Variables**: snake_case (`call_llm`, `prep_res`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_SIZE_BYTES`)
- **Node Classes**: Suffix with `Node`
- **Model Classes**: Descriptive names (`Persona`, `DebateMessage`)

### Type Hints

Use type hints for all function signatures:
```python
def call_llm(prompt: str, temperature: float = 0.7) -> str:
    ...

def load_personas(path: str) -> list[Persona]:
    ...
```

### Persona Configuration

Personas are defined in YAML with per-agent temperature:
```yaml
personas:
  - name: "The Architect"
    role: "Systems Design Expert"
    focus: "Structure, scalability, patterns"
    temperature: 0.8  # Higher = more creative
    style: |
      Multi-line description of behavior...
```

### File Handling

Validate file sizes before processing:
```python
WARN_SIZE_BYTES = 1 * 1024 * 1024   # 1 MB - warn user
MAX_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB - reject

if file_size > MAX_SIZE_BYTES:
    raise ValueError(f"File too large: {file_size / 1024 / 1024:.1f} MB")
```

## Key Dependencies

- `pocketflow>=0.0.1` - Flow orchestration framework
- `anthropic>=0.15.0` - Claude API client
- `pyyaml>=6.0` - YAML parsing for structured outputs
