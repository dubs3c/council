# Context Management Development Plan

## Purpose

Improve context handling without making the code hard to follow. The system should keep the full discussion transcript as the source of truth, but avoid asking later LLM calls to repeatedly interpret a long raw history when a smaller, structured view is enough.

The intended flow is:

1. Agents create full initial proposals.
2. Each debate round appends each agent's action, reasoning, and optional revision.
3. The system reconstructs each agent's current proposal from the initial proposal plus revisions.
4. Before consensus, each agent's discussion is summarized independently.
5. Consensus is generated from the per-agent summaries and current proposals.
6. Long discussions can compact older turns into per-agent summaries while keeping the full transcript intact.
7. Prompt caching is enabled where providers support it, using stable prompt sections first.

## Design Principles

- Keep the full transcript append-only.
- Keep derived context separate from stored history.
- Prefer simple data structures over framework-heavy abstractions.
- Make prompt construction deterministic and readable.
- Preserve each agent's viewpoint separately until the final consensus step.
- Add provider-specific prompt caching only behind a small compatibility layer.
- Do not send provider-specific cache fields to providers that may reject them.

## Target Data Flow

The implementation should make it easy to answer two questions at any point:

1. What happened in the full discussion?
2. What does each agent currently believe?

Use the append-only transcript for the first question and derived helpers for the second.

```text
Initial proposals
  + debate messages
  -> current proposals by agent
  -> per-agent summaries
  -> final consensus
```

Do not store a second mutable copy of each agent's current proposal in shared state unless there is a concrete reason. Reconstructing from initial proposals plus revisions keeps the state easier to reason about and avoids drift between stored copies.

## Stage 1: Fix Revision State

Goal: make proposal revisions safe and deterministic.

Tasks:

- Replace remaining `updated_proposal` references with `proposal_revision` logic.
- Add one shared helper for applying a revision to a proposal.
- Add one shared helper for reconstructing current proposals from initial proposals and debate messages.
- Use those helpers in `DebateNode` and `DiscussionState`.
- Make revision semantics explicit in the debate prompt.

Recommended semantics for now:

- `summary` replaces the prior summary when present.
- `analysis` replaces the full prior analysis list when present.
- `recommendations` replaces the full prior recommendation list when present.
- Omitted fields are unchanged.

Example:

```json
{
  "proposal_revision": {
    "summary": "Use a smaller staged rollout."
  }
}
```

This changes only the summary. Existing analysis and recommendations remain unchanged.

Example:

```json
{
  "proposal_revision": {
    "recommendations": [
      "Start with one pilot persona.",
      "Measure context size per turn."
    ]
  }
}
```

This replaces the full recommendation list. It does not append to the previous list.

Prompt text should say this directly so the model does not assume list fields are patches.

Acceptance criteria:

- A summary-only revision preserves prior analysis and recommendations.
- Multiple revisions by the same agent apply in order.
- Revisions by different agents do not affect each other.
- `DiscussionState.get_current_proposals()` works after revisions.
- `ruff check .` and `pytest -q` pass.

## Stage 2: Add Small Context Helpers

Goal: avoid duplicating reconstruction and formatting logic across nodes.

Add a small module, likely `src/council/context.py`, with pure helper functions:

```python
def apply_revision(base: Proposal, revision: ProposalRevision) -> Proposal:
    ...


def get_current_proposals(
    proposals: list[Proposal],
    debate_messages: list[DebateMessage],
) -> dict[str, Proposal]:
    ...


def get_agent_messages(
    agent: str,
    debate_messages: list[DebateMessage],
) -> list[DebateMessage]:
    ...
```

Rules:

- Helpers must not mutate inputs.
- Helpers must not call LLMs.
- Ordering should be stable and easy to inspect.
- Keep helpers small; do not introduce a large context manager class unless it becomes clearly necessary.

Implementation detail:

- `apply_revision()` should return a new `Proposal` instance.
- `get_current_proposals()` should start from the initial proposal list, then walk `debate_messages` in order.
- If a revision is found for an agent without an initial proposal, ignore it or raise a clear `ValueError`. Prefer raising during tests, but be careful not to break production fallback paths unexpectedly.
- Preserve the original proposal `turn` unless there is a clear need to expose the latest revision turn. If needed later, add a separate field rather than overloading `Proposal.turn`.

Acceptance criteria:

- `DebateNode` uses shared helpers for current proposal reconstruction.
- `DiscussionState` delegates to the same reconstruction helper.
- Unit tests cover helper behavior directly.

## Stage 3: Add Per-Agent Summaries

Goal: summarize each agent independently before final consensus.

Add a model similar to:

```python
@dataclass
class AgentDiscussionSummary:
    agent: str
    initial_position: str
    revision_history: list[str]
    current_position: str
    concerns_raised: list[str]
    agreements: list[str]
    unresolved_concerns: list[str]
    final_stance: str
```

Add an `AgentSummaryNode` that runs once per agent after debate and before consensus.

Input per agent:

- Original prompt.
- The agent's initial proposal.
- The agent's debate messages.
- Current reconstructed proposal.
- Optionally the full debate history for context, with instructions to summarize only the target agent.

Recommended first implementation:

- Include all debate messages in the summarizer prompt for correctness.
- Tell the model to summarize only the target agent.
- Do not attempt relevance filtering in the first pass. Filtering can accidentally remove important disagreements, and it is not necessary until context pressure is proven.

Output:

- One `AgentDiscussionSummary` per agent, stored as `shared["agent_summaries"]`.

Fallback behavior:

- If summarization fails, create a deterministic fallback summary from the initial proposal, current proposal, and that agent's messages.
- Do not block the whole run because one summary failed.

Fallback summary shape:

- `initial_position`: initial proposal summary.
- `revision_history`: markdown or short strings from that agent's revision messages.
- `current_position`: reconstructed current proposal summary.
- `concerns_raised`: concerns from that agent's `CONCERN` messages.
- `agreements`: agreement targets from that agent's `AGREE` messages.
- `unresolved_concerns`: empty list unless there is a direct concern message to carry forward.
- `final_stance`: simple statement derived from the latest action.

Keep fallback text plain and conservative. It should not invent conclusions.

Suggested JSON contract for the LLM:

```json
{
  "agent": "Agent Name",
  "initial_position": "...",
  "revision_history": ["..."],
  "current_position": "...",
  "concerns_raised": ["..."],
  "agreements": ["..."],
  "unresolved_concerns": ["..."],
  "final_stance": "..."
}
```

Acceptance criteria:

- One summary is generated per persona.
- Summaries remain separated by agent.
- Tests mock LLM responses and validate parsing.
- Tests cover fallback summary generation.

## Stage 4: Refactor Consensus Input

Goal: make consensus synthesis use structured agent summaries instead of relying on raw debate history alone.

Consensus prompt should include:

- Original prompt.
- Current proposal for each agent.
- Independent summary for each agent.
- Agreement map, if available.
- Explicit unresolved concerns or dissent.

Consensus prompt should avoid blending all agent history into one undifferentiated summary.

Important consensus instruction:

- Do not treat an idea as consensus unless the summaries or agreement map show support from the relevant agents.
- Preserve dissent explicitly when an agent's final stance remains conditional or opposed.
- Use current proposals as the final state, but use revision history to explain how the council got there.

Recommended prompt shape:

```text
## Original Question

...

## Current Proposals By Agent

### Agent A
...

### Agent B
...

## Independent Agent Summaries

### Agent A
...

### Agent B
...

## Task

Synthesize consensus from the independent summaries. Preserve dissent where it remains.
```

Acceptance criteria:

- `ConsensusNode` uses `agent_summaries` when available.
- Current proposals are included separately from summaries.
- Tests assert agent summaries appear as separate sections in the consensus prompt.
- Existing short discussions still work.

Fallback behavior:

- If `agent_summaries` is missing, `ConsensusNode` may fall back to the current raw discussion formatting.
- The fallback should be explicit in code and covered by one test.
- Do not silently mix both paths in a way that makes prompt content hard to predict.

## Stage 5: Add Simple Context Compaction

Goal: prevent very long debates from sending all old raw turns every round.

Keep this simple at first.

Recommended config:

```python
context_compaction_enabled: bool = True
compact_after_turns: int = 8
recent_turns_to_keep: int = 3
```

Behavior:

- Never delete or mutate `shared["debate_messages"]`.
- For debate prompts, include initial proposals, current proposals, compacted per-agent summaries, and only recent raw turns.
- Compact only older turns.
- Keep recent turns verbatim so agents can respond to fresh details.

Compaction boundary example:

- `current_turn = 12`
- `recent_turns_to_keep = 3`
- Older compacted range: turns 1 through 9
- Recent raw range: turns 10 through 12

If compaction runs at the beginning of turn 12, the exact boundary may be turns 1 through 8 compacted and turns 9 through 11 raw, depending on whether the current turn has produced messages yet. Pick one convention and test it directly.

Recommended convention:

- During `DebateNode.prep()`, compact completed turns only.
- If preparing turn 12 and keeping 3 recent completed turns, keep turns 9, 10, and 11 raw.
- Compact turns 1 through 8.

Debate prompt after compaction:

```text
## Original Question

...

## Initial Proposals

...

## Current Proposals

...

## Older Debate Summary By Agent

...

## Recent Debate

...
```

Acceptance criteria:

- Full transcript output is unchanged.
- Old raw turns are omitted from debate prompts after compaction.
- Older context is still represented as per-agent summaries.
- Recent turns remain verbatim.
- Tests cover the compaction boundary.

Keep compaction implementation local and simple at first:

- Add a helper that decides which messages are compacted and which remain raw.
- Reuse `AgentSummaryNode` logic or the same summary prompt shape where possible.
- Store compacted context as a small structure in shared state, for example `shared["compacted_context"]`.
- Include `through_turn` so future prompt construction knows what has already been summarized.
- Do not add token counting in this stage unless needed. Turn-count compaction is enough for the first implementation.

## Stage 6: Add Prompt Parts For Caching

Goal: support prompt caching without complicating node logic.

Add a tiny prompt representation, likely in `src/council/prompts.py`:

```python
@dataclass(frozen=True)
class PromptPart:
    name: str
    content: str
    cacheable: bool = False


@dataclass(frozen=True)
class Prompt:
    parts: list[PromptPart]

    def to_text(self) -> str:
        return "\n\n".join(part.content for part in self.parts if part.content)
```

Keep `call_llm()` compatible with plain strings. Accept either `str` or `Prompt`.

Prompt construction rule:

- Stable sections first.
- Changing sections last.
- Cacheable sections must be deterministic byte-for-byte.

Determinism requirements:

- Do not put timestamps in cacheable prompt parts.
- Keep persona ordering stable.
- Keep proposal ordering stable.
- Avoid dict iteration unless the dict was built from an already ordered source.
- Do not include incidental debug text in cacheable sections.

Good cacheable sections:

- Persona instructions.
- Original prompt.
- File content.
- Initial proposals.
- Compacted older summaries.
- Final per-agent summaries.

Usually non-cacheable sections:

- Current turn instructions.
- Recent raw debate.
- Current reconstructed proposals if they change every round.

For debate prompts, current reconstructed proposals may still benefit from automatic prefix caching when they do not change, but mark them non-cacheable initially because they are derived from revisions and can change every turn.

Acceptance criteria:

- Existing `call_llm(str, ...)` call sites still work.
- New prompt objects flatten to deterministic text.
- Tests verify part ordering and text output.

## Stage 7: Provider-Safe Prompt Caching

Goal: enable caching where possible without breaking OpenAI-compatible providers.

Add provider config fields:

```python
prompt_cache: bool = False
prompt_cache_strategy: str = "none"
```

Initial supported strategies:

- `none`: flatten prompt and send normally.
- `openai_compatible_auto`: flatten prompt and rely on provider-side automatic prefix caching if available.

Do not add Anthropic-specific cache-control request fields to the current OpenAI-compatible request path unless a native Anthropic provider path is added.

Acceptance criteria:

- Default behavior is unchanged.
- OpenAI-compatible requests remain valid.
- Cacheable prompt parts are kept before volatile parts.
- Tests assert no unsupported provider fields are sent by default.

Implementation detail:

- `call_llm()` can accept `prompt: str | Prompt`.
- If it receives `Prompt`, flatten it with `prompt.to_text()` before the OpenAI-compatible call.
- Keep cache metadata on `PromptPart` for future provider implementations, but do not send it in the current request body.
- Add a narrow helper such as `render_prompt(prompt: str | Prompt) -> str` so request-building code remains easy to read.

## Stage 8: Output Updates

Goal: make reports transparent without changing the source transcript.

Report should include:

- Final consensus.
- Independent agent summaries.
- Full discussion transcript in the existing collapsible section.
- Optional compaction note if compaction was used.

Acceptance criteria:

- Each agent summary appears separately.
- Full transcript remains available.
- Partial revisions are displayed as revisions, not misleading full proposals.

Report detail:

- The report should not hide the raw debate because summaries can be imperfect.
- If compacted context was used internally, mention that only prompt context was compacted; the transcript below is complete.
- Keep the output formatting simple markdown. Avoid adding complex report rendering helpers unless output code becomes difficult to read.

## Flow Wiring

Keep the flow easy to inspect.

Initial target:

```text
Input -> Proposal -> Debate loop -> AgentSummary -> Consensus -> Output
```

After compaction:

```text
Input -> Proposal -> Debate loop with optional compaction in prep -> AgentSummary -> Consensus -> Output
```

Prefer adding compaction inside debate prompt preparation before adding a separate node. A separate `ContextCompactionNode` is only worth it if the flow remains clearer with it.

Shared keys to introduce:

- `agent_summaries`: per-agent summary objects created after debate.
- `compacted_context`: optional compacted older debate summaries for long debate prompts.

Shared keys to keep as source-of-truth:

- `proposals`
- `debate_messages`

Do not add `current_proposals` as mutable shared state in the first implementation. Use helpers to derive it when needed.

## Implementation Order

1. Fix stale revision state and add reconstruction tests.
2. Add small context helpers.
3. Add `AgentDiscussionSummary` and `AgentSummaryNode`.
4. Wire summaries before consensus.
5. Refactor consensus prompt to use summaries and current proposals.
6. Update report output to include summaries.
7. Add simple compaction for long debates.
8. Add prompt parts.
9. Add provider-safe prompt caching flags and behavior.

## Testing Checklist

- Revision helper preserves omitted fields.
- Multiple revisions apply in order.
- Current proposal reconstruction works for multiple agents.
- `DiscussionState.get_current_proposals()` works after revisions.
- Agent summaries are generated independently.
- Summary fallback works when LLM output is invalid or unavailable.
- Consensus prompt keeps agent summaries separate.
- Compaction keeps recent turns and summarizes older turns.
- Full transcript output remains complete.
- Prompt part flattening is deterministic.
- Provider caching defaults do not change request payload compatibility.

Specific regression tests to add early:

- `DiscussionState.get_current_proposals()` no longer references `updated_proposal`.
- Consensus prompt includes `Agent A` and `Agent B` summaries under separate headings.
- A summary-only revision does not clear analysis or recommendations.
- A recommendations revision replaces the prior list and does not append.
- Compaction does not change the number of stored debate messages.

Run after each Python change:

```bash
ruff check .
pytest -q
```

## Definition Of Done

- Initial proposals and debate messages remain append-only.
- Current proposals are reconstructed deterministically.
- Consensus is generated from per-agent summaries and current proposals.
- Long debates can compact older context without deleting transcript history.
- Prompt construction supports stable cacheable sections.
- Prompt caching is opt-in and provider-safe.
- The implementation remains easy to read, with small helpers and minimal new abstractions.
- `ruff check .` passes.
- `pytest -q` passes.
