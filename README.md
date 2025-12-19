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

---

# Telegram Voice Orchestrator (OATL)

Remote voice-to-text orchestration via Telegram with 100% local processing.

## Overview

The Voice Orchestrator allows you to:
1. Send voice messages to a Telegram bot from anywhere
2. Have them automatically transcribed locally using Whisper (GPU-accelerated)
3. Feed transcripts to the Narrative Artifact Pipeline

**Key Principles:**
- **Data Sovereignty** - All processing happens locally; Telegram is just a channel
- **Explicit State** - Session state persisted as JSON for auditability
- **Immutability** - Sessions are locked after finalization

## Prerequisites

- NVIDIA GPU with CUDA support (recommended: RTX 3050+ with 4GB+ VRAM)
- Telegram Bot Token (from @BotFather)
- Your Telegram Chat ID

## Configuration

Add to your `.env` file:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_ALLOWED_CHAT_ID=your-chat-id

# Whisper Configuration
WHISPER_MODEL=small.en  # Options: tiny, base, small, small.en, medium, large
WHISPER_DEVICE=cuda     # cuda or cpu
WHISPER_FP16=true       # Use FP16 for faster GPU inference

# Sessions Directory
SESSIONS_DIR=./sessions
```

## Running the Daemon

```bash
# Start the voice orchestrator daemon
python -m src.cli.daemon

# With verbose logging
python -m src.cli.daemon --verbose
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Start new voice capture session |
| `/done` or `/finish` | Finalize session and begin transcription |
| `/status` | Show current session status |
| `/transcripts` | Retrieve transcription text |
| `/process` | Send transcripts to narrative pipeline |
| `/list` | List session files |
| `/get <file>` | Download specific file |
| `/help` | Show available commands |

## Typical Workflow

1. **Start a session:**
   - Send `/start` to the bot
   - Bot confirms session creation with ID

2. **Record voice notes:**
   - Send voice messages one at a time
   - Bot confirms receipt with sequence number

3. **Finalize and transcribe:**
   - Send `/done` to finalize
   - Bot transcribes all audio locally using Whisper
   - Progress updates sent for each file

4. **Review results:**
   - `/transcripts` - View all transcriptions
   - `/list` - See session files
   - `/get transcripts/001_audio.txt` - Download specific file

5. **Process through pipeline (optional):**
   - `/process` - Run narrative pipeline on transcripts
   - Bot sends results when complete

## Session Structure

```
sessions/
└── {session-id}/           # e.g., 2025-12-18_14-30-00
    ├── metadata.json       # Session state and audio entries
    ├── audio/
    │   ├── 001_audio.ogg
    │   ├── 002_audio.ogg
    │   └── ...
    ├── transcripts/
    │   ├── 001_audio.txt
    │   ├── 002_audio.txt
    │   └── consolidated.txt
    └── process/
        ├── input.txt       # Consolidated for pipeline
        └── output/         # Pipeline artifacts
```

## Session States

| State | Description |
|-------|-------------|
| `COLLECTING` | Session open, accepting voice messages |
| `TRANSCRIBING` | Finalized, transcription in progress |
| `TRANSCRIBED` | All audio transcribed, ready for processing |
| `PROCESSING` | Downstream pipeline running |
| `PROCESSED` | All processing complete |
| `ERROR` | Unrecoverable error occurred |

## Interactive UI Features (005-telegram-ux-overhaul)

The bot includes an enhanced interactive experience with inline keyboards:

### Zero-Command Flow
- Sessions auto-create when you send your first voice message
- Inline keyboard buttons replace most text commands
- **Finalize**, **Status**, and **Help** buttons available on all messages

### Progress Feedback
- Real-time progress updates during transcription
- Visual progress bar: `▓▓▓▓▓░░░░░ 50%`
- Step descriptions for each processing phase

### Error Recovery
- User-friendly error messages (no stack traces)
- Recovery buttons for common issues
- Retry option for transient failures

### Session Protection
- Confirmation dialog when starting new session with active audio
- Options: Finalize current, Start new, or Return to active

### Timeout Handling
- Notification for long-running operations
- Options to continue waiting or cancel

### Preferences
- `/preferences` - View/change UI settings
- `/preferences simple` - Enable simplified UI (no emojis)
- `/preferences normal` - Enable normal UI (with emojis)

### Help System
- Contextual help button in all keyboards
- Help content varies based on current operation