"""Downstream processor for session transcripts.

This module handles the integration with the existing narrative pipeline,
consolidating transcripts and invoking the main pipeline.
"""

import logging
from pathlib import Path
from typing import Optional

from src.models.session import Session, SessionState
from src.services.session.manager import SessionManager

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when downstream processing fails."""

    pass


class DownstreamProcessor:
    """
    Process transcribed sessions through the narrative pipeline.

    Follows contracts/downstream-processor.md interface.
    """

    def __init__(self, session_manager: SessionManager):
        """
        Initialize the downstream processor.

        Args:
            session_manager: SessionManager for state updates
        """
        self.session_manager = session_manager

    def consolidate_transcripts(self, session: Session) -> Path:
        """
        Consolidate all transcripts into a single input file.

        Creates process/input.txt with header and transcript content.

        Args:
            session: Session with completed transcripts

        Returns:
            Path to consolidated input file
        """
        sessions_dir = self.session_manager.sessions_dir
        transcripts_dir = session.transcripts_path(sessions_dir)
        process_dir = session.process_path(sessions_dir)
        process_dir.mkdir(exist_ok=True)

        # Build consolidated content
        lines = [
            f"# Voice Session: {session.id}",
            f"# Created: {session.created_at.isoformat()}",
            f"# Audio files: {session.audio_count}",
            "",
            "---",
            "",
        ]

        for audio_entry in session.audio_entries:
            if audio_entry.transcript_filename:
                transcript_path = transcripts_dir / audio_entry.transcript_filename
                if transcript_path.exists():
                    text = transcript_path.read_text(encoding="utf-8").strip()
                    lines.append(f"## Audio {audio_entry.sequence}")
                    if audio_entry.duration_seconds:
                        lines.append(f"Duration: {audio_entry.duration_seconds:.1f}s")
                    lines.append("")
                    lines.append(text)
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        input_path = process_dir / "input.txt"
        input_path.write_text("\n".join(lines), encoding="utf-8")

        logger.info(f"Consolidated transcripts to {input_path}")
        return input_path

    def process(self, session: Session, provider: str = "deepseek") -> Path:
        """
        Invoke the narrative pipeline with consolidated transcripts.

        Args:
            session: Session to process
            provider: LLM provider to use

        Returns:
            Path to output directory

        Raises:
            ProcessingError: If processing fails
        """
        if session.state != SessionState.TRANSCRIBED:
            raise ProcessingError(
                f"Session must be in TRANSCRIBED state, not {session.state.value}"
            )

        sessions_dir = self.session_manager.sessions_dir
        process_dir = session.process_path(sessions_dir)
        output_dir = process_dir / "output"
        output_dir.mkdir(exist_ok=True)

        # Consolidate transcripts
        input_path = self.consolidate_transcripts(session)

        # Import here to avoid circular imports
        from src.cli.main import run as run_pipeline

        try:
            # Run the narrative pipeline
            logger.info(f"Starting narrative pipeline for session {session.id}")

            result = run_pipeline(
                input_path=str(input_path),
                output_dir=str(output_dir),
                provider=provider,
                verbose=False,
            )

            if result != 0:
                raise ProcessingError(f"Pipeline returned non-zero exit code: {result}")

            logger.info(f"Pipeline completed for session {session.id}")
            return output_dir

        except Exception as e:
            logger.exception(f"Pipeline failed for session {session.id}: {e}")
            raise ProcessingError(f"Pipeline execution failed: {e}") from e

    def list_outputs(self, session: Session) -> list[Path]:
        """
        List all output files from downstream processing.

        Args:
            session: Session to list outputs for

        Returns:
            List of output file paths
        """
        sessions_dir = self.session_manager.sessions_dir
        output_dir = session.process_path(sessions_dir) / "output"

        if not output_dir.exists():
            return []

        outputs = []
        for item in output_dir.iterdir():
            if item.is_file():
                outputs.append(item)
            elif item.is_dir():
                # Include files from subdirectories
                for subitem in item.rglob("*"):
                    if subitem.is_file():
                        outputs.append(subitem)

        return sorted(outputs)
