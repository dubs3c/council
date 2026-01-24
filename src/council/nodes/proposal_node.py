"""Proposal node for generating initial agent proposals."""

from pocketflow import BatchNode

from council.console import print_proposal, print_warning
from council.models import AnalysisPoint, Persona, Proposal
from council.utils import call_llm, parse_json_response


class ProposalNode(BatchNode):
    """BatchNode for generating initial proposals from each agent.

    Runs in parallel - each agent independently analyzes the prompt/file
    and produces a structured proposal from their persona's perspective.
    """

    def prep(self, shared):
        """Prepare inputs for each agent."""
        prompt = shared["prompt"]
        file_content = shared.get("file_content")
        personas = shared["personas"]

        # Create an input for each persona
        inputs = []
        for persona in personas:
            inputs.append(
                {
                    "persona": persona,
                    "prompt": prompt,
                    "file_content": file_content,
                    "show_stream": shared["config"]["show_stream"],
                }
            )

        return inputs

    def exec(self, prep_res):
        """Generate proposal for a single agent."""
        persona: Persona = prep_res["persona"]
        prompt = prep_res["prompt"]
        file_content = prep_res["file_content"]

        # Build the LLM prompt
        file_section = ""
        if file_content:
            file_section = f"""

## File Content to Analyze

```
{file_content}
```
"""

        llm_prompt = f"""{persona.to_prompt()}

## Your Task

Analyze the following and provide your initial proposal.

## User's Question/Request

{prompt}
{file_section}

## Instructions

Provide your analysis as a structured proposal. Consider this from your unique perspective as {{
            persona.name
        }} ({persona.role}).

Return your response as JSON with this structure:

{{"summary": "A brief 1-2 sentence summary of your position",
  "analysis": [
    {{"point": "First key observation or finding", "reasoning": "Why this matters from your perspective"}},
    {{"point": "Second key observation or finding", "reasoning": "Why this matters from your perspective"}},
    {{"point": "Third key observation or finding", "reasoning": "Why this matters from your perspective"}}
  ],
  "recommendations": ["First recommendation", "Second recommendation", "Third recommendation"]
}}

Focus on what matters most from your perspective. Be specific and actionable."""

        # Call LLM with persona's temperature and provider
        response = call_llm(
            llm_prompt,
            temperature=persona.temperature,
            provider=persona.provider,
        )

        # Parse JSON response
        parsed = parse_json_response(response)

        # Validate required fields
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed)}")
        if "summary" not in parsed:
            raise ValueError("Missing 'summary' in response")
        if "analysis" not in parsed:
            raise ValueError("Missing 'analysis' in response")
        if "recommendations" not in parsed:
            raise ValueError("Missing 'recommendations' in response")

        # Build Proposal object
        analysis_points = []
        for item in parsed["analysis"]:
            analysis_points.append(
                AnalysisPoint(point=item["point"], reasoning=item["reasoning"])
            )

        proposal = Proposal(
            agent=persona.name,
            summary=parsed["summary"].strip(),
            analysis=analysis_points,
            recommendations=parsed["recommendations"],
            turn=0,
        )

        return {
            "proposal": proposal,
            "persona_name": persona.name,
            "show_stream": prep_res["show_stream"],
        }

    def exec_fallback(self, prep_res, exc):
        """Handle LLM failures gracefully."""
        persona = prep_res["persona"]
        print_warning(f"{persona.name} failed to generate proposal: {exc}")

        # Return a minimal fallback proposal
        return {
            "proposal": Proposal(
                agent=persona.name,
                summary="[Failed to generate proposal due to an error]",
                analysis=[
                    AnalysisPoint(point="Error occurred", reasoning=str(exc))
                ],
                recommendations=["Retry the analysis"],
                turn=0,
            ),
            "persona_name": persona.name,
            "show_stream": prep_res["show_stream"],
        }

    def post(self, shared, prep_res, exec_res_list):
        """Collect all proposals and update shared state."""
        proposals = []
        show_stream = shared["config"]["show_stream"]

        for result in exec_res_list:
            if result and result.get("proposal"):
                proposal = result["proposal"]
                proposals.append(proposal)

                if show_stream:
                    print_proposal(proposal.agent, proposal.to_markdown())

        shared["proposals"] = proposals
        shared["current_turn"] = 0

        return "default"
