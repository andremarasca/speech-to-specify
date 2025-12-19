# Research: Telegram Voice Orchestrator (OATL)

**Feature Branch**: `002-telegram-voice-orchestrator`  
**Created**: 2025-12-18  
**Purpose**: Resolve technical unknowns and establish best practices before implementation

## 1. python-telegram-bot Library

### Decision
Use `python-telegram-bot` v22+ with `ApplicationBuilder` pattern for async bot implementation.

### Rationale
- **Fully async**: Native asyncio support avoids blocking I/O during file downloads
- **Builder pattern**: Clean configuration without complex constructor chains
- **Built-in resilience**: Automatic retry and reconnection for network failures
- **Rich handler ecosystem**: MessageHandler with filters for voice messages, CommandHandler for /start, /finish
- **Active maintenance**: Well-documented, frequent updates, large community

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| aiogram | Different API conventions, smaller ecosystem |
| telethon | Client library (user accounts), overkill for bot use |
| pyTelegramBotAPI | Primarily synchronous, less mature async support |

### Implementation Pattern

```python
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

async def handle_voice(update: Update, context):
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    await file.download_to_drive(local_path)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", handle_start))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
```

### Key Configuration
- **Bot Token**: Environment variable `TELEGRAM_BOT_TOKEN`
- **Allowed Users**: Single-user authorization via chat_id whitelist
- **Timeouts**: Read timeout 30s, connect timeout 10s for file downloads

---

## 2. OpenAI Whisper Local Installation

### Decision
Use `whisper small.en` model with FP16 precision on CUDA device.

### Rationale
- **RTX 3050 (4GB VRAM)**: `small` model uses ~2GB VRAM, fits comfortably with headroom
- **`medium` model**: Exceeds 4GB, would cause CPU fallback and 10x slower inference
- **`.en` variant**: English-only optimized model has better accuracy than multilingual
- **FP16 precision**: Halves memory usage and runs faster on RTX Tensor Cores

### Model Comparison (RTX 3050)

| Model | VRAM | Speed | Accuracy | Fit? |
|-------|------|-------|----------|------|
| tiny | 1GB | Very fast | Low | ✅ |
| base | 1GB | Fast | Medium | ✅ |
| **small.en** | **~2GB** | **Good** | **High** | **✅ SELECTED** |
| medium | 5GB | Slow | Very high | ❌ Exceeds VRAM |
| large | 10GB | Very slow | Highest | ❌ Way exceeds |

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| faster-whisper | CTranslate2 dependency adds complexity; marginal speed gain |
| OpenAI Whisper API | Cost per minute, latency, privacy violation (cloud processing) |
| whisper.cpp | C++ build complexity on Windows; Python wrapper immature |

### Implementation Pattern

```python
import whisper

model = whisper.load_model("small.en", device="cuda")

def transcribe(audio_path: str) -> str:
    result = model.transcribe(audio_path, fp16=True)
    return result["text"]
```

### Key Configuration
- **Model cache**: `~/.cache/whisper/` or custom `WHISPER_CACHE_DIR`
- **Device**: Explicit `device="cuda"` to force GPU
- **Pre-load model**: Load once at daemon startup, reuse for all transcriptions

---

## 3. Session State Management

### Decision
Atomic JSON file writes using temp file + `os.replace()` pattern.

### Rationale
- **Atomic guarantee**: `os.replace()` is POSIX-atomic on same filesystem
- **No partial writes**: Crash during write leaves old file intact
- **Pure stdlib**: No external dependencies (no SQLite, Redis, etc.)
- **Human-readable**: JSON files inspectable with any text editor

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| SQLite | Overkill for single-user; adds query complexity |
| Redis | External service dependency; violates local-only principle |
| pickle | Security risk (arbitrary code execution); not human-readable |
| Direct file.write() | Non-atomic; partial writes possible on crash |

### Implementation Pattern

```python
import os
import json
import tempfile

def save_session_state(session_dir: Path, state: dict):
    target_path = session_dir / "metadata.json"
    
    # Write to temp file in same directory (same filesystem)
    fd, tmp_path = tempfile.mkstemp(dir=session_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, indent=2)
        # Atomic replace
        os.replace(tmp_path, target_path)
    except:
        os.unlink(tmp_path)  # Cleanup on failure
        raise
```

### Session Folder Structure

```text
sessions/
└── 2025-12-18_14-30-00/
    ├── metadata.json        # Session state (atomic updates)
    ├── audio/
    │   ├── 001_audio.ogg
    │   ├── 002_audio.ogg
    │   └── 003_audio.ogg
    ├── transcripts/
    │   ├── 001_audio.txt
    │   ├── 002_audio.txt
    │   └── 003_audio.txt
    └── process/
        ├── input.txt        # Consolidated transcripts
        └── output/          # Downstream processor results
```

---

## 4. Downstream Integration Pattern

### Decision
Direct Python function import from existing `src.cli.main` module (not subprocess).

### Rationale
- **No IPC overhead**: Direct function call, shared memory
- **Native types**: No string serialization/deserialization
- **Better errors**: Real Python stack traces instead of exit codes
- **Testable**: Easy to mock in unit tests

### Alternatives Considered

| Alternative | When to Use Instead |
|-------------|---------------------|
| subprocess | When isolation is critical (untrusted code) |
| multiprocessing | When parallel CPU-bound work needed |

### Implementation Pattern

The existing `src.cli.main.run()` function expects `argparse.Namespace`. Create adapter:

```python
from argparse import Namespace
from pathlib import Path

def invoke_narrative_pipeline(input_file: Path, output_dir: Path) -> int:
    """Invoke existing narrative pipeline with consolidated transcript."""
    args = Namespace(
        input_file=str(input_file),
        output_dir=str(output_dir),
        provider=None,  # Use default
        verbose=False
    )
    
    # Import at call time to avoid circular deps
    from src.cli.main import run
    return run(args)
```

### Integration Flow

1. Session reaches "transcribed" state
2. Consolidate all transcripts into `process/input.txt`
3. Call `invoke_narrative_pipeline(input_file, session_dir / "process" / "output")`
4. Narrative pipeline writes artifacts to output directory
5. Update session state to "processed"

---

## 5. Error Handling Strategy

### Decision
Fail-fast with explicit error states in session metadata.

### Rationale
- **Deterministic**: No retries with exponential backoff (non-deterministic timing)
- **Auditable**: All errors logged with timestamp and context
- **Recoverable**: Session remains valid; user can retry specific operations

### Error Categories

| Category | Handling | Session Impact |
|----------|----------|----------------|
| Telegram connection lost | Log + continue locally | None (pending commands queued) |
| Audio download failed | Log error in metadata | Session valid, audio marked failed |
| Transcription failed | Log + continue others | Session valid, file marked failed |
| Downstream processor failed | Log + preserve transcribed state | Session stays "transcribed" |

---

## Summary: Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Bot Framework | python-telegram-bot | 22.x |
| Speech-to-Text | openai-whisper | 20231117 |
| GPU Acceleration | PyTorch + CUDA | 2.x + 12.x |
| State Persistence | JSON + atomic writes | stdlib |
| CLI Integration | Direct import | N/A |
| Testing | pytest + pytest-asyncio | 8.x |
