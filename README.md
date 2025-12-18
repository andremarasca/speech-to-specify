# Narrative Artifact Pipeline

A system to transform chaotic text into structured narrative artifacts through a deterministic 3-step LLM prompt chain.

## Overview

The Narrative Artifact Pipeline takes unstructured text input (brainstorms, notes, ideas) and processes it through three sequential transformation steps:

1. **Constitution** - Establishes the fundamental principles and constraints for the narrative
2. **Specification** - Transforms principles into detailed requirements and features
3. **Planning** - Creates an actionable implementation plan

Each step produces a self-documenting artifact with full metadata, enabling future comprehension without external context.

## Installation

### Prerequisites

- Python 3.12+
- An OpenAI or Anthropic API key

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd speech-to-specify

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.\.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Configure your preferred LLM provider:

```bash
# For OpenAI (default)
OPENAI_API_KEY=sk-your-api-key-here
NARRATE_PROVIDER=openai

# For Anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
NARRATE_PROVIDER=anthropic
```

## Usage

### Basic Usage

```bash
python -m src.cli.main path/to/your/notes.txt
```

### Options

```bash
python -m src.cli.main <input-file> [options]

Options:
  -o, --output-dir DIR    Directory for outputs (default: ./output)
  -p, --provider NAME     LLM provider: openai, anthropic, mock (default: openai)
  -v, --verbose           Show detailed progress
  -V, --version           Show version
```

### Examples

```bash
# Process with OpenAI (default)
python -m src.cli.main ./notes/brainstorm.txt

# Use Anthropic instead
python -m src.cli.main ./notes/brainstorm.txt --provider anthropic

# Verbose output with custom output directory
python -m src.cli.main ./notes/brainstorm.txt --output-dir ./my-artifacts --verbose

# Test with mock provider (no API key needed)
python -m src.cli.main ./notes/brainstorm.txt --provider mock --verbose
```

## Output Structure

After running the pipeline, outputs are organized as:

```
output/
└── executions/
    └── {execution-id}/
        ├── input.md              # Original input with metadata
        ├── execution.json        # Execution metadata and status
        ├── artifacts/
        │   ├── 01_constitution.md
        │   ├── 02_specification.md
        │   └── 03_planning.md
        └── logs/
            └── llm_traffic.jsonl # Full LLM interaction log
```

### Artifact Format

Each artifact includes a self-documenting YAML header:

```markdown
---
id: abc123
execution_id: exec-456
step_number: 1
step_name: constitution
predecessor_id: null
created_at: 2024-01-15T10:30:00Z
---

# Constitution

[Generated content here]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error (bad arguments) |
| 2 | Configuration error (missing API key) |
| 3 | Validation error (empty input) |
| 4 | LLM error (API failure) |
| 5 | Internal error |

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=src --cov-report=term-missing
```

### Project Structure

```
src/
├── cli/           # Command-line interface
├── lib/           # Shared utilities
├── models/        # Domain entities
└── services/
    ├── llm/       # LLM provider adapters
    └── persistence/  # Storage implementations
tests/
├── unit/          # Unit tests
├── contract/      # Contract tests for interfaces
└── integration/   # End-to-end tests
prompts/           # LLM prompt templates
```

## License

See [LICENSE](LICENSE) for details.