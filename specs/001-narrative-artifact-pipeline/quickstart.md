# Quickstart: Constituidor de Artefatos Narrativos

## Prerequisites

- Python 3.12+
- Git
- API key for OpenAI or Anthropic (optional for testing with mock provider)

## Setup (5 minutes)

### 1. Clone and enter repository

```bash
cd c:\Projects\speech-to-specify
```

### 2. Create virtual environment

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure environment

Create `.env` file in repository root:

```env
# Required: Choose one provider
OPENAI_API_KEY=sk-your-openai-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Optional: Defaults shown
NARRATE_PROVIDER=openai
NARRATE_OUTPUT_DIR=./output
```

### 5. Verify installation

```bash
# Run tests (91+ tests)
python -m pytest tests/ -v

# Check CLI
python -m src.cli.main --help
```

### 6. Quick test with mock provider (no API key needed)

```bash
python -m src.cli.main sample_input.txt --provider mock --verbose
```

## First Execution

### 1. Create sample input

Create `sample_input.txt`:

```
Ontem eu estava pensando sobre como organizar minhas ideias de projeto.
Tenho várias coisas na cabeça: primeiro, quero fazer um app de notas,
mas também pensei em algo para gerenciar tarefas. Talvez pudesse ser
a mesma coisa? Não sei. O importante é que seja simples de usar.
Ah, e precisa funcionar offline também. Acho que React Native seria
bom para isso. Ou Flutter? Preciso pesquisar mais.
```

### 2. Run the pipeline

```bash
python -m src.cli.main sample_input.txt --verbose
```

### 3. Inspect output

```bash
# List generated artifacts
ls output/executions/*/artifacts/

# View first artifact
cat output/executions/*/artifacts/01_constitution.md

# View LLM logs
cat output/executions/*/logs/llm_traffic.jsonl
```

## Development Workflow

### Run tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_models.py

# Contract tests only
pytest tests/contract/
```

### Code formatting

```bash
# Format
black src/ tests/

# Check only
black --check src/ tests/
```

### Type checking

```bash
mypy src/
```

## Project Structure Overview

```
src/
├── models/         # Domain entities (Input, Artifact, Execution, etc.)
├── services/
│   ├── orchestrator.py    # Main pipeline logic
│   ├── llm/              # LLM provider adapters
│   └── persistence/      # File storage
├── cli/            # Command-line interface
└── lib/            # Shared utilities (config, timestamps)

tests/
├── unit/           # Pure logic tests
├── contract/       # Interface compliance tests
└── integration/    # End-to-end with fixtures
```

## Common Tasks

### Add a new LLM provider

1. Create `src/services/llm/new_provider.py`
2. Implement `LLMProvider` protocol
3. Register in `src/services/llm/__init__.py`
4. Add contract tests

### Modify prompt templates

Edit files in `prompts/` directory. Templates use placeholders:

- `{{input}}` - Original input text
- `{{previous_artifact}}` - Content from previous step
- `{{constitution}}` - Constitution context (step 1 only)

### Debug execution issues

1. Check `output/executions/{id}/logs/llm_traffic.jsonl` for API interactions
2. Check `output/executions/{id}/logs/failure.json` if execution failed
3. Run with `--verbose` for detailed progress

## Troubleshooting

### "Missing required environment variable"

Ensure `.env` file exists and contains required API key.

### "LLM request failed: rate limit"

Wait and retry. Consider using different provider or reducing request frequency.

### Tests fail with import errors

Ensure virtual environment is activated and dependencies installed:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Output directory permission error

Ensure `output/` directory is writable or specify different path:

```bash
python -m src.cli.main input.txt --output-dir /tmp/narrate-output
```

## Next Steps

1. Read [spec.md](spec.md) for full requirements
2. Review [data-model.md](data-model.md) for entity details
3. Check contracts in [contracts/](contracts/) for interface specifications
4. Run `/speckit.tasks` to generate implementation tasks
