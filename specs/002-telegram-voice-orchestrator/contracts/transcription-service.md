# Contract: Transcription Service

**Module**: `src/services/transcription/`  
**Purpose**: Convert audio files to text using local Whisper model

## Interface

### TranscriptionService

```python
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class TranscriptionResult:
    text: str
    language: str  # Detected or configured language
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None

class TranscriptionService(ABC):
    @abstractmethod
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        pass
    
    @abstractmethod
    def load_model(self) -> None:
        """
        Load Whisper model into memory.
        Should be called once at daemon startup.
        Raises: ModelLoadError if CUDA not available or model download fails.
        """
        pass
    
    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe single audio file.
        Audio must be in supported format (ogg, mp3, wav, m4a).
        """
        pass
    
    @abstractmethod
    def transcribe_batch(
        self, 
        audio_paths: list[Path],
        on_progress: Optional[Callable[[int, int], None]] = None
    ) -> list[TranscriptionResult]:
        """
        Transcribe multiple audio files sequentially.
        on_progress(completed, total) called after each file.
        """
        pass
    
    @abstractmethod
    def unload_model(self) -> None:
        """Release model from memory."""
        pass
```

## Implementation: WhisperTranscriptionService

### Model Selection

| Attribute | Value |
|-----------|-------|
| Model | `small.en` |
| Device | `cuda` (forced) |
| FP16 | `True` |
| Language | English (auto-detect disabled for speed) |

### Supported Audio Formats

- `.ogg` (Telegram native)
- `.mp3`
- `.wav`
- `.m4a`
- `.webm`

Unsupported formats raise `UnsupportedAudioFormatError`.

## Configuration

```python
class TranscriptionConfig:
    model_name: str = "small.en"  # WHISPER_MODEL env var
    device: str = "cuda"  # Force GPU
    fp16: bool = True
    cache_dir: Optional[Path] = None  # WHISPER_CACHE_DIR env var
```

## Error Handling

| Error | Handling |
|-------|----------|
| CUDA not available | Raise `CudaNotAvailableError` at startup |
| Model download fails | Raise `ModelLoadError` with retry instructions |
| Corrupted audio | Return `TranscriptionResult(success=False, error_message="...")` |
| OOM during inference | Raise `OutOfMemoryError` (caller should retry with smaller batch) |

## Performance Expectations

| Audio Length | Expected Time | Notes |
|--------------|---------------|-------|
| 1 minute | ~10 seconds | RTX 3050, small.en, FP16 |
| 5 minutes | ~45 seconds | |
| 10 minutes | ~90 seconds | |

## Usage Pattern

```python
# At daemon startup
transcription_service = WhisperTranscriptionService(config)
transcription_service.load_model()  # Load once, reuse

# Per session finalization
results = transcription_service.transcribe_batch(
    audio_paths=[session_path / "audio" / f for f in audio_files],
    on_progress=lambda done, total: notify_user(f"Transcribing {done}/{total}")
)

# At daemon shutdown
transcription_service.unload_model()
```

## Output Files

Transcription results saved to `{session}/transcripts/{sequence:03d}_audio.txt`:

```text
[Transcript of voice message recorded at 2025-12-18T14:31:15Z]

This is the transcribed text from the audio file. It preserves
the natural flow of speech without artificial formatting.
```

## Testing Contract

```python
def test_transcription_service_contract():
    # GIVEN a loaded transcription service
    service = get_transcription_service()
    assert service.is_ready()
    
    # WHEN transcribing a valid audio file
    result = service.transcribe(Path("test_audio.ogg"))
    
    # THEN result contains text
    assert result.success
    assert len(result.text) > 0
    assert result.duration_seconds > 0
```
