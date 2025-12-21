# Data Model: Async Audio Response Pipeline

**Feature**: 008-async-audio-response  
**Date**: 2025-12-21  
**Status**: Complete

## Entities

### TTSRequest

Representa uma solicitação de síntese de áudio.

```python
@dataclass
class TTSRequest:
    """Request for TTS synthesis.
    
    Attributes:
        text: Text content to synthesize (will be sanitized)
        session_id: Session identifier for storage path
        sequence: LLM response sequence number (aligns with llm_responses/)
        oracle_name: Oracle name for filename
        oracle_id: Oracle identifier for idempotency key
    """
    text: str
    session_id: str
    sequence: int
    oracle_name: str
    oracle_id: str
    
    @property
    def idempotency_key(self) -> str:
        """Generate unique key for deduplication."""
        content = f"{self.session_id}:{self.oracle_id}:{self.text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @property
    def filename(self) -> str:
        """Generate filename following llm_responses pattern."""
        safe_name = self.oracle_name.lower().replace(" ", "_")
        return f"{self.sequence:03d}_{safe_name}.ogg"
```

**Validation Rules**:
- `text` não pode ser vazio
- `sequence` deve ser > 0
- `session_id` deve seguir formato `YYYY-MM-DD_HH-MM-SS`

### TTSResult

Representa o resultado de uma operação de síntese.

```python
@dataclass
class TTSResult:
    """Result from TTS synthesis operation.
    
    Attributes:
        success: Whether synthesis completed successfully
        file_path: Path to generated audio file (if success)
        error_message: Error description (if failed)
        duration_ms: Time taken for synthesis in milliseconds
        cached: Whether result was returned from cache (idempotent)
    """
    success: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    cached: bool = False
    
    @classmethod
    def ok(cls, file_path: Path, duration_ms: int, cached: bool = False) -> "TTSResult":
        """Create successful result."""
        return cls(success=True, file_path=file_path, duration_ms=duration_ms, cached=cached)
    
    @classmethod
    def error(cls, message: str, duration_ms: int = 0) -> "TTSResult":
        """Create failed result."""
        return cls(success=False, error_message=message, duration_ms=duration_ms)
    
    @classmethod
    def timeout(cls, timeout_seconds: int) -> "TTSResult":
        """Create timeout result."""
        return cls(success=False, error_message=f"Synthesis timed out after {timeout_seconds}s")
```

**State Transitions**:
```
Request → Synthesizing → Success (file_path set)
                      → Failed (error_message set)
                      → Timeout (error_message set)
         Cached     → Success (cached=True)
```

### TTSArtifact

Representa um arquivo de áudio persistido (para tracking e GC).

```python
@dataclass
class TTSArtifact:
    """Persisted TTS audio artifact.
    
    Used for garbage collection tracking.
    
    Attributes:
        file_path: Absolute path to audio file
        session_id: Associated session
        sequence: LLM response sequence
        oracle_id: Oracle that generated the source text
        created_at: When the artifact was created
        file_size_bytes: Size of the audio file
        idempotency_key: Hash for deduplication
    """
    file_path: Path
    session_id: str
    sequence: int
    oracle_id: str
    created_at: datetime
    file_size_bytes: int
    idempotency_key: str
    
    @property
    def age_hours(self) -> float:
        """Calculate artifact age in hours."""
        delta = datetime.utcnow() - self.created_at
        return delta.total_seconds() / 3600
    
    def is_expired(self, retention_hours: int) -> bool:
        """Check if artifact exceeds retention period."""
        return self.age_hours > retention_hours
```

### TTSConfig

Configuração do serviço TTS (adicionada a `src/lib/config.py`).

```python
class TTSConfig(BaseSettings):
    """Configuration for Text-to-Speech service.
    
    Per Constitution Principle III (External Configuration):
    All TTS parameters must be externally configurable.
    """
    
    enabled: bool = Field(
        default=True,
        alias="TTS_ENABLED",
        description="Enable/disable TTS synthesis",
    )
    
    voice: str = Field(
        default="pt-BR-AntonioNeural",
        alias="TTS_VOICE",
        description="Edge TTS voice identifier",
    )
    
    format: str = Field(
        default="ogg",
        alias="TTS_FORMAT",
        description="Audio output format: ogg, mp3, wav",
    )
    
    timeout_seconds: int = Field(
        default=60,
        alias="TTS_TIMEOUT_SECONDS",
        description="Maximum time for synthesis operation",
    )
    
    max_text_length: int = Field(
        default=5000,
        alias="TTS_MAX_TEXT_LENGTH",
        description="Maximum text length to synthesize",
    )
    
    # Garbage Collection
    gc_retention_hours: int = Field(
        default=24,
        alias="TTS_GC_RETENTION_HOURS",
        description="Hours to retain TTS artifacts before GC",
    )
    
    gc_max_storage_mb: int = Field(
        default=500,
        alias="TTS_GC_MAX_STORAGE_MB",
        description="Maximum storage for TTS artifacts in MB",
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }
```

## Relationships

```
Session (existing)
    │
    ├── llm_responses/           # Existing: Oracle text responses
    │   └── {seq}_{oracle}.txt
    │
    └── audio/
        ├── {seq}_voice.ogg      # Existing: User voice input
        └── tts/                  # NEW: TTS audio output
            └── {seq}_{oracle}.ogg
                    │
                    └── TTSArtifact (tracks for GC)

TTSRequest ───synthesize()──→ TTSResult
     │                              │
     └── idempotency_key ──────────→ cached=True (if exists)
```

## Storage Schema

### Session Directory Structure (Extended)

```
sessions/{session_id}/
├── metadata.json              # Existing
├── audio/
│   ├── 001_voice.ogg          # Existing: User voice input
│   ├── 002_voice.ogg
│   └── tts/                   # NEW
│       ├── 001_cetico.ogg     # TTS for llm_responses/001_cetico.txt
│       └── 002_pragmatico.ogg # TTS for llm_responses/002_pragmatico.txt
├── llm_responses/
│   ├── 001_cetico.txt
│   └── 002_pragmatico.txt
└── transcripts/
    ├── 001_voice.txt
    └── 002_voice.txt
```

### File Naming Convention

| Component | Pattern | Example |
|-----------|---------|---------|
| TTS Audio | `{seq:03d}_{oracle_name}.{format}` | `001_cetico.ogg` |
| Alignment | Matches `llm_responses/{seq}_{oracle}.txt` | `001_cetico.txt` |

## Validation Rules

### TTSRequest Validation

| Field | Rule | Error |
|-------|------|-------|
| text | Non-empty after sanitization | "Text cannot be empty" |
| text | Length ≤ TTSConfig.max_text_length | "Text exceeds maximum length" |
| sequence | > 0 | "Sequence must be positive" |
| session_id | Matches `\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}` | "Invalid session ID format" |

### TTSConfig Validation

| Field | Rule | Error |
|-------|------|-------|
| voice | Non-empty | "Voice must be specified" |
| format | In ['ogg', 'mp3', 'wav'] | "Unsupported audio format" |
| timeout_seconds | > 0 | "Timeout must be positive" |
| gc_retention_hours | ≥ 1 | "Retention must be at least 1 hour" |

## Integration with Existing Models

### Session Model Extension

Adicionar método helper em `Session` (opcional, para conveniência):

```python
# In src/models/session.py

def tts_path(self, sessions_root: Path) -> Path:
    """Get the path to the TTS audio subdirectory."""
    return self.audio_path(sessions_root) / "tts"
```

### No Changes Required To

- `Session` dataclass (estrutura principal)
- `LlmEntry` (referência por sequence number)
- `AudioEntry` (áudios de entrada são separados)
- `metadata.json` schema (TTS artifacts são derivados, não persistidos em metadata)
