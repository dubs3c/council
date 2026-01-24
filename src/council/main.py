#!/usr/bin/env python3
"""The Council - Multi-agent discussion system for reaching consensus.

A council of AI agents with distinct personas analyze prompts and files,
debate their perspectives, and reach consensus through structured discussion.
"""

import argparse
import sys

from council.console import print_error, print_info
from council.flow import run_council


def main():
    """Main entry point for The Council CLI."""
    parser = argparse.ArgumentParser(
        description="The Council - Multi-agent consensus through discussion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python main.py --prompt "What are the pros and cons of microservices?"

  # Analyze a file
  python main.py --prompt "Review this architecture" --file ./arch.md

  # Custom personas and settings
  python main.py --prompt "Evaluate this design" --file ./design.py \\
    --personas ./my_personas.yaml --max-turns 5 --show-stream

  # Save report to specific directory
  python main.py --prompt "Analyze this code" --file ./api.py \\
    --output-dir ./reports
""",
    )

    # Required arguments
    parser.add_argument(
        "--prompt",
        "-p",
        type=str,
        required=True,
        help="The question or request for the council to discuss",
    )

    # Optional arguments
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Path to a file to analyze (optional)",
    )

    parser.add_argument(
        "--personas",
        type=str,
        default=None,
        help="Path to custom personas YAML file (default: config/default_personas.yaml)",
    )

    parser.add_argument(
        "--max-turns",
        "-t",
        type=int,
        default=3,
        help="Maximum number of debate rounds (default: 3)",
    )

    parser.add_argument(
        "--show-stream",
        "-s",
        action="store_true",
        help="Print the discussion as it happens",
    )

    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=".",
        help="Directory to save the report (default: current directory)",
    )

    args = parser.parse_args()

    # Validate prompt
    if not args.prompt.strip():
        print_error("--prompt cannot be empty")
        sys.exit(1)

    # Run the council
    try:
        run_council(
            prompt=args.prompt,
            file_path=args.file,
            personas_path=args.personas,
            max_turns=args.max_turns,
            show_stream=args.show_stream,
            output_dir=args.output_dir,
        )

        # Exit with success
        sys.exit(0)

    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(1)
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print_info("\n\nSession interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if args.show_stream:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
