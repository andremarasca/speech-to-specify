"""Shared pytest fixtures for all test types."""

import pytest
import tempfile
import shutil
from pathlib import Path

from src.lib.timestamps import generate_id


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp(prefix="narrate_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_input_content() -> str:
    """Sample chaotic text for testing."""
    return """
    Então temos essa ideia de fazer um sistema que pega texto todo bagunçado
    e transforma em coisa organizada usando IA. A gente quer que seja tipo
    uma pipeline, sabe? Primeiro faz uma coisa, depois outra, e no final
    tem uns documentos bem estruturados. 
    
    Precisa funcionar com OpenAI e Anthropic, mas sem ficar preso em nenhum.
    E tem que guardar tudo que aconteceu, tipo um log completo.
    """


@pytest.fixture
def execution_id() -> str:
    """Generate a test execution ID."""
    return generate_id()


@pytest.fixture
def mock_llm_response() -> str:
    """Standard mock LLM response for testing."""
    return """# Constitution

## Core Principles

1. **Determinism**: The system shall produce predictable, reproducible results.
2. **Auditability**: All operations shall be logged and traceable.
3. **Modularity**: Components shall be loosely coupled and independently testable.
"""
