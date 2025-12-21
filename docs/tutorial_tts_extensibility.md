# Tutorial: TTS Extensibility

This tutorial covers the extensibility points of the async audio response pipeline.

## Overview

The TTS (Text-to-Speech) system converts oracle text feedback into audio messages that are delivered asynchronously after the text response. This design ensures text delivery is never blocked by audio synthesis.

## 1. Synthesis Logic Location

The synthesis logic is organized in `src/services/tts/`:

```
src/services/tts/
├── __init__.py           # Module exports
├── base.py               # TTSService abstract base class
├── edge_tts_service.py   # Microsoft Edge TTS implementation
├── mock_service.py       # Mock service for testing
├── text_sanitizer.py     # Text preprocessing
└── garbage_collector.py  # Artifact lifecycle management
```

### Key Components

- **TTSService** (`base.py`): Abstract base class defining the synthesis interface
- **EdgeTTSService** (`edge_tts_service.py`): Production implementation using Microsoft Edge TTS
- **MockTTSService** (`mock_service.py`): Test double for unit/integration testing
- **TextSanitizer** (`text_sanitizer.py`): Preprocesses text by removing markdown formatting

### Synthesis Flow

1. Oracle callback triggers `_synthesize_and_send_audio()` in daemon
2. Text is sanitized (markdown removed, special chars stripped)
3. TTSRequest is created with idempotency key (session_id + oracle_id + text hash)
4. If cached file exists, return immediately (idempotent)
5. Otherwise, synthesize via edge-tts with configurable timeout
6. On success, send voice message via Telegram
7. On failure, log error but never block text delivery

## 2. TTS Provider Extension Points

### Creating a Custom Provider

To add a new TTS provider, implement the `TTSService` abstract class:

```python
from src.services.tts.base import TTSService
from src.models.tts import TTSRequest, TTSResult

class MyCustomTTSService(TTSService):
    """Custom TTS provider implementation."""
    
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Synthesize speech from text.
        
        Args:
            request: TTSRequest with text, session_id, oracle_id, sequence
            
        Returns:
            TTSResult with success status and artifact path
        """
        # 1. Check idempotency - return cached if exists
        artifact_path = self.get_artifact_path(request)
        if artifact_path.exists() and artifact_path.stat().st_size > 0:
            return TTSResult.ok(artifact_path, duration_ms=0, cached=True)
        
        # 2. Implement your synthesis logic
        try:
            # ... your provider-specific code here ...
            audio_bytes = await my_provider.synthesize(request.text)
            
            # 3. Persist to artifact path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(audio_bytes)
            
            return TTSResult.ok(artifact_path, duration_ms=elapsed)
            
        except Exception as e:
            return TTSResult.error(str(e), duration_ms=elapsed)
    
    async def check_health(self) -> bool:
        """Verify provider connectivity."""
        return await my_provider.ping()
```

### Provider Registration

Register your provider in the daemon's `_init_tts_service()`:

```python
def _init_tts_service(self) -> Optional[TTSService]:
    config = get_tts_config()
    if not config.enabled:
        return None
    
    # Factory pattern allows swapping providers
    provider = os.getenv("TTS_PROVIDER", "edge")
    
    if provider == "edge":
        return EdgeTTSService(config, self.sessions_path)
    elif provider == "custom":
        return MyCustomTTSService(config, self.sessions_path)
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")
```

### Contract Compliance

New providers must pass the contract tests in `tests/contract/test_tts_service_contract.py`:

- **BC-TTS-001**: Async non-blocking with timeout
- **BC-TTS-002**: Idempotency (same request → same file)
- **BC-TTS-003**: Error isolation (return TTSResult.error, never raise)
- **BC-TTS-004**: Text cleaning via TextSanitizer
- **BC-TTS-005**: Correct file persistence path
- **BC-TTS-006**: Configuration respect

## 3. Codec Configuration

### Supported Audio Formats

The system supports three audio formats configured via `TTS_FORMAT`:

| Format | Extension | Use Case |
|--------|-----------|----------|
| `ogg` | `.ogg` | Default, good compression, Telegram native |
| `mp3` | `.mp3` | Wide compatibility |
| `wav` | `.wav` | Lossless, larger files |

### Configuration

Set the format in your environment:

```bash
# .env
TTS_FORMAT=ogg  # Options: ogg, mp3, wav
```

### Edge TTS Codec Mapping

EdgeTTSService maps formats to edge-tts output formats:

```python
FORMAT_MAPPING = {
    "ogg": "audio-ogg-vorbis-128k",
    "mp3": "audio-24khz-48kbitrate-mono-mp3",
    "wav": "riff-24khz-16bit-mono-pcm",
}
```

## 4. Performance Tuning

### Timeout Configuration

Control synthesis timeout to prevent slow requests from blocking:

```bash
TTS_TIMEOUT_SECONDS=60  # Maximum time for synthesis (default: 60s)
```

**Recommendations:**
- Short texts (<500 chars): 30 seconds
- Medium texts (500-2000 chars): 60 seconds
- Long texts (>2000 chars): 90-120 seconds

### Text Length Limits

Prevent excessive processing with text length limits:

```bash
TTS_MAX_TEXT_LENGTH=5000  # Maximum text length to synthesize
```

Texts exceeding this limit will be truncated before synthesis.

### Garbage Collection Tuning

Balance storage usage vs artifact retention:

```bash
TTS_GC_RETENTION_HOURS=24  # Hours to keep artifacts (0 = no age cleanup)
TTS_GC_MAX_STORAGE_MB=500  # Maximum storage in MB (0 = no storage limit)
```

**Recommendations by use case:**
- Personal bot: `retention=168` (1 week), `storage=100`
- Shared bot: `retention=24` (1 day), `storage=500`
- High-traffic: `retention=6`, `storage=1000`

### Voice Selection

Choose the TTS voice via configuration:

```bash
TTS_VOICE=pt-BR-AntonioNeural  # Edge TTS voice identifier
```

Available Brazilian Portuguese voices:
- `pt-BR-AntonioNeural` (male, default)
- `pt-BR-FranciscaNeural` (female)
- `pt-BR-BrendaNeural` (female)
- `pt-BR-HumbertoNeural` (male)

See [Edge TTS voice list](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts#prebuilt-neural-voices) for all available voices.

## 5. Storage Path Configuration

### Artifact Storage Structure

TTS artifacts are stored within session directories:

```
sessions/
└── {session_id}/
    └── audio/
        └── tts/
            ├── 001_cetico.ogg
            ├── 002_pragmatico.ogg
            └── 003_visionario.ogg
```

### Path Components

- **session_id**: Auto-generated timestamp (e.g., `2025-12-21_12-00-00`)
- **sequence**: LLM response sequence number (001, 002, ...)
- **oracle_id**: Oracle that generated the source text
- **format**: Configured audio format extension

### Custom Base Path

The sessions path is configured via SessionConfig:

```bash
SESSIONS_PATH=./sessions  # Base path for all session data
```

### Accessing Artifact Paths

Use `TTSService.get_artifact_path()` to get the correct path:

```python
path = tts_service.get_artifact_path(request)
# Returns: Path("sessions/{session_id}/audio/tts/{seq}_{oracle}.{format}")
```

## Troubleshooting

### Common Issues

**Audio not generated:**
1. Check `TTS_ENABLED=true`
2. Verify edge-tts is installed: `pip show edge-tts`
3. Check network connectivity to Microsoft TTS service
4. Review daemon logs for synthesis errors

**Audio delayed or slow:**
1. Increase `TTS_TIMEOUT_SECONDS`
2. Check network latency to TTS service
3. Consider shorter text segments

**Storage growing unbounded:**
1. Enable garbage collection: `TTS_GC_RETENTION_HOURS=24`
2. Set storage limit: `TTS_GC_MAX_STORAGE_MB=500`
3. Review artifacts in `sessions/*/audio/tts/`

### Debug Logging

Enable debug logging for TTS module:

```python
import logging
logging.getLogger("src.services.tts").setLevel(logging.DEBUG)
```

## Related Documentation

- [spec.md](../specs/008-async-audio-response/spec.md): Feature specification
- [plan.md](../specs/008-async-audio-response/plan.md): Technical plan
- [contracts/tts-service.md](../specs/008-async-audio-response/contracts/tts-service.md): Service contracts
