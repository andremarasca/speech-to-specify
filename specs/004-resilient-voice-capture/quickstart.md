# Quickstart: Resilient Voice Capture

**Feature**: 004-resilient-voice-capture  
**Date**: 2025-12-19  
**Purpose**: Get developers up and running quickly

## Prerequisites

- Python 3.11+
- CUDA-capable GPU (optional, CPU fallback available)
- ~5GB disk space (Whisper model + embeddings model)
- Telegram bot token (for Telegram interface)

## Setup

### 1. Clone and Install

```bash
# Clone repository
git clone <repo-url>
cd speech-to-specify

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings:
# TELEGRAM_BOT_TOKEN=your_token_here
# WHISPER_MODEL=small.en
# WHISPER_DEVICE=cuda  # or 'cpu'
# SESSIONS_DIR=./sessions
```

### 3. Verify Installation

```bash
# Run tests
pytest tests/ -v

# Check Whisper model loads
python -c "from src.services.transcription.whisper import WhisperTranscriptionService; print('OK')"

# Check embedding model loads  
python -c "from src.lib.embedding import get_embedding_service; get_embedding_service().embed('test'); print('OK')"
```

## Project Structure

```
src/
├── models/
│   ├── session.py          # Session, AudioSegment, etc.
│   └── search_result.py    # SearchResult model
├── services/
│   ├── session/
│   │   ├── manager.py      # SessionLifecycleService
│   │   ├── storage.py      # Atomic JSON persistence
│   │   └── matcher.py      # Session resolution
│   ├── transcription/
│   │   ├── whisper.py      # Whisper integration
│   │   └── queue.py        # Async queue
│   ├── search/
│   │   ├── engine.py       # SearchService
│   │   └── indexer.py      # Embedding indexer
│   └── help/
│       └── registry.py     # Command registry
├── cli/
│   └── commands.py         # Command implementations
└── lib/
    ├── embedding.py        # EmbeddingService
    ├── checksum.py         # File integrity
    └── config.py           # Configuration
```

## Key Components

### Session Model

```python
from src.models.session import Session, SessionState, AudioEntry

# Sessions are managed via SessionManager
from src.services.session.manager import SessionManager
from src.services.session.storage import SessionStorage

storage = SessionStorage(Path("./sessions"))
manager = SessionManager(storage)

# Create session
session = manager.create_session(chat_id=123)
print(f"Created: {session.id}")  # "2025-12-19_14-30-00"

# Finalize session
result = manager.finalize_session(session.id)
print(result.message)  # "✅ Session finalized..."

# Reopen session
result = manager.reopen_session(session.id)
print(f"Epoch: {result.reopen_epoch}")  # 1
```

### Audio Capture

```python
from src.services.audio.capture import AudioCaptureService

capture = AudioCaptureService(storage)

# Add audio chunk
segment = capture.add_audio_chunk(
    session_id="2025-12-19_14-30-00",
    audio_data=audio_bytes,
    timestamp=datetime.now()
)
print(f"Segment {segment.sequence}: {segment.checksum}")
```

### Search

```python
from src.services.search.engine import SearchService

search = SearchService(storage)

# Semantic search
response = search.search("project roadmap discussion")
for result in response.results:
    print(f"{result.session_name}: {result.relevance_score:.2f}")
    for fragment in result.preview_fragments:
        print(f"  ...{fragment.text}...")

# Chronological listing
sessions = search.list_chronological(limit=10)
```

### Transcription Queue

```python
from src.services.transcription.queue import TranscriptionQueueService

queue = TranscriptionQueueService(storage, whisper_service)

# Start background worker
queue.start_worker()

# Queue session for transcription
result = queue.queue_session("2025-12-19_14-30-00")
print(f"Queued: {result.queued_count} segments")

# Check progress
progress = queue.get_session_progress("2025-12-19_14-30-00")
print(f"Progress: {progress.progress_percent:.0f}%")
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Contract tests only
pytest tests/contract/ -v

# Integration tests
pytest tests/integration/ -v

# Specific test file
pytest tests/contract/test_session_lifecycle.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Common Tasks

### Add a New Command

1. Create handler in `src/cli/commands.py`:
```python
@command("/mycommand")
@description("Do something useful")
@param("arg", "Description of arg")
@example("/mycommand foo")
async def cmd_mycommand(ctx: Context, arg: str):
    # Implementation
    pass
```

2. Add contract test in `tests/contract/test_help_system.py`:
```python
def test_mycommand_registered():
    assert help_system.get_handler("/mycommand") is not None
```

### Add a New Service

1. Define interface in `specs/004-resilient-voice-capture/contracts/`
2. Create implementation in `src/services/`
3. Add contract tests in `tests/contract/`
4. Add integration tests in `tests/integration/`

### Debug Transcription Issues

```bash
# Check queue status
python -c "from src.services.transcription.queue import get_queue; print(get_queue().get_queue_status())"

# Check specific session
python -c "from src.services.transcription.queue import get_queue; print(get_queue().get_session_progress('SESSION_ID'))"

# Retry failed segments
python -c "from src.services.transcription.queue import get_queue; print(get_queue().retry_failed('SESSION_ID'))"
```

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Filesystem storage | Auditable JSON files per constitution |
| Atomic writes | temp file + os.replace prevents corruption |
| Local embeddings | Privacy: no cloud dependency |
| Async transcription | UI responsiveness per Pillar II |
| Dual search index | Fallback ensures search always works (Pillar V) |

## Next Steps

1. Read [spec.md](spec.md) for full requirements
2. Read [data-model.md](data-model.md) for entity details
3. Read contracts in `contracts/` for service interfaces
4. Run `pytest tests/contract/` to understand expected behavior
