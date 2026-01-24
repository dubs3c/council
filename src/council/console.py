"""Rich console utilities for The Council CLI output."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

# Global console instance
console = Console()


def print_header(title: str, subtitle: str = None) -> None:
    """Print a styled header for major sections."""
    console.print()
    console.print(Rule(title, style="bold cyan"))
    if subtitle:
        console.print(Text(subtitle, style="dim"))
    console.print()


def print_section(title: str, style: str = "bold yellow") -> None:
    """Print a section divider."""
    console.print()
    console.print(Rule(title, style=style))


def print_council_header(
    prompt: str, file_path: str = None, personas: list = None, max_turns: int = 3
) -> None:
    """Print the main Council header at session start."""
    console.print()
    console.print(
        Panel(
            Text("THE COUNCIL", justify="center", style="bold white"),
            style="cyan",
            padding=(1, 2),
        )
    )

    info_lines = [f"[bold]Prompt:[/bold] {prompt[:100]}..."]
    if file_path:
        info_lines.append(f"[bold]File:[/bold] {file_path}")
    if personas:
        agent_names = ", ".join(p.name for p in personas)
        info_lines.append(f"[bold]Agents:[/bold] {agent_names}")
    info_lines.append(f"[bold]Max turns:[/bold] {max_turns}")

    console.print(Panel("\n".join(info_lines), style="dim"))
    console.print()


def print_proposal(agent: str, content: str) -> None:
    """Print a styled proposal from an agent."""
    console.print()
    console.print(
        Panel(
            Markdown(content),
            title=f"[bold green]INITIAL PROPOSAL: {agent}[/bold green]",
            border_style="green",
        )
    )


def print_debate_turn(turn: int) -> None:
    """Print a debate turn header."""
    console.print()
    console.print(Rule(f"DEBATE - Turn {turn}", style="bold magenta"))


def print_debate_message(agent: str, content: str) -> None:
    """Print a debate message from an agent."""
    console.print(
        Panel(
            Markdown(content),
            title=f"[bold magenta]{agent}[/bold magenta]",
            border_style="magenta",
        )
    )


def print_consensus_start() -> None:
    """Print the consensus synthesis header."""
    console.print()
    console.print(Rule("MODERATOR: Synthesizing consensus...", style="bold blue"))


def print_consensus_status(message: str) -> None:
    """Print a consensus status update."""
    console.print(f"[blue]{message}[/blue]")


def print_consensus_feedback(feedback: list[dict]) -> None:
    """Print agent feedback on consensus."""
    for f in feedback:
        status = "[green]approved[/green]" if f["approved"] else "[red]requested changes[/red]"
        console.print(f"  - [bold]{f['agent']}[/bold]: {status}")


def print_final_consensus(content: str) -> None:
    """Print the final consensus report."""
    console.print()
    console.print(
        Panel(
            Markdown(content),
            title="[bold blue]FINAL CONSENSUS[/bold blue]",
            border_style="blue",
        )
    )


def print_session_complete(
    summary: str = None, recommendations: list = None, filepath: str = None
) -> None:
    """Print the session complete summary."""
    console.print()
    console.print(
        Panel(
            Text("COUNCIL SESSION COMPLETE", justify="center", style="bold white"),
            style="green",
            padding=(1, 2),
        )
    )

    if summary:
        console.print()
        console.print(Panel(summary, title="[bold]Summary[/bold]", border_style="dim"))

    if recommendations:
        high_priority = [r for r in recommendations if r.priority == "high"][:3]
        if high_priority:
            console.print()
            console.print("[bold]Top Recommendations:[/bold]")
            for i, rec in enumerate(high_priority, 1):
                console.print(f"  [cyan]{i}.[/cyan] {rec.action}")

    if filepath:
        console.print()
        console.print(f"[dim]Full report saved to:[/dim] [bold]{filepath}[/bold]")
    console.print()


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[dim]{message}[/dim]")


def print_special_event(message: str) -> None:
    """Print a special event (consensus reached, max turns, etc.)."""
    console.print()
    console.print(f"[bold yellow]*** {message} ***[/bold yellow]")
