"""CLI entry point for the narrative pipeline."""

import argparse
import sys
from pathlib import Path

from src import __version__
from src.models import Input
from src.services.orchestrator import NarrativePipeline
from src.services.llm import get_provider
from src.services.persistence import create_artifact_store, create_log_store
from src.lib.config import get_settings
from src.lib.exceptions import (
    NarrativeError,
    ConfigError,
    ValidationError,
    LLMError,
    PersistenceError,
)


# Exit codes per CLI contract
EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_VALIDATION_ERROR = 3
EXIT_LLM_ERROR = 4
EXIT_INTERNAL_ERROR = 5


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="narrate",
        description="Transform chaotic text into structured narrative artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  narrate ./notes/brainstorm.txt
  narrate ./notes/brainstorm.txt --output-dir ./my-artifacts
  narrate ./notes/brainstorm.txt --provider anthropic --verbose
        """,
    )
    
    # Required arguments
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to input file containing chaotic text (.txt, .md)",
    )
    
    # Optional arguments
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help="Directory for execution outputs (default: ./output)",
    )
    
    parser.add_argument(
        "-p", "--provider",
        type=str,
        default=None,
        choices=["openai", "anthropic", "mock"],
        help="LLM provider to use (default: openai)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress during execution",
    )
    
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    return parser


def run(args: argparse.Namespace) -> int:
    """
    Run the narrative pipeline with the given arguments.
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Exit code
    """
    settings = get_settings()
    
    # Resolve configuration (CLI args override env vars)
    output_dir = args.output_dir or settings.output_dir
    provider_name = args.provider or settings.llm_provider
    verbose = args.verbose or settings.verbose
    
    # Validate input file exists
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    
    if not input_path.is_file():
        print(f"Error: Path is not a file: {args.input_file}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    
    # Validate provider configuration
    try:
        settings.validate_provider_config(provider_name)
    except ConfigError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    
    # Load input
    try:
        input_data = Input.from_file(args.input_file)
    except ValidationError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    
    # Create components
    try:
        provider = get_provider(provider_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    
    artifact_store = create_artifact_store(output_dir)
    log_store = create_log_store(output_dir)
    
    # Create and run pipeline
    pipeline = NarrativePipeline(
        provider=provider,
        artifact_store=artifact_store,
        log_store=log_store,
        verbose=verbose,
    )
    
    try:
        execution = pipeline.execute(input_data)
        
        if verbose:
            print(f"  Duration: {_format_duration(execution)}")
            print(f"  Artifacts: {execution.total_steps}")
            print(f"  LLM calls: {execution.total_steps}")
        
        return EXIT_SUCCESS
        
    except ValidationError as e:
        print(f"Error: Input validation failed: {e.message}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    
    except LLMError as e:
        print(f"Error: LLM request failed: {e.message}", file=sys.stderr)
        return EXIT_LLM_ERROR
    
    except PersistenceError as e:
        print(f"Error: Storage error: {e.message}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    
    except NarrativeError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


def _format_duration(execution) -> str:
    """Format execution duration for display."""
    if execution.started_at and execution.completed_at:
        duration = (execution.completed_at - execution.started_at).total_seconds()
        return f"{duration:.1f}s"
    return "N/A"


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
