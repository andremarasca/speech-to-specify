````markdown
# Contract: Error Catalog

**Feature**: 005-telegram-ux-overhaul  
**Module**: `src/lib/error_catalog.py`  
**Date**: 2025-12-19

## Purpose

Error Catalog provides externalized error definitions for humanized user messages. It enforces Constitution Principle V (Externalized Configuration) by keeping all user-facing error messages in configuration rather than hardcoded in source code.

## Structure

```python
from src.models.ui_state import UserFacingError, ErrorSeverity, RecoveryAction

ERROR_CATALOG: dict[str, UserFacingError] = {
    # Storage Errors (ERR_STORAGE_xxx)
    "ERR_STORAGE_001": UserFacingError(...),
    "ERR_STORAGE_002": UserFacingError(...),
    
    # Network Errors (ERR_NETWORK_xxx)
    "ERR_NETWORK_001": UserFacingError(...),
    
    # Transcription Errors (ERR_TRANSCRIPTION_xxx)
    "ERR_TRANSCRIPTION_001": UserFacingError(...),
    
    # Session Errors (ERR_SESSION_xxx)
    "ERR_SESSION_001": UserFacingError(...),
    
    # Telegram Errors (ERR_TELEGRAM_xxx)
    "ERR_TELEGRAM_001": UserFacingError(...),
    
    # Config Errors (ERR_CONFIG_xxx)
    "ERR_CONFIG_001": UserFacingError(...),
}

DEFAULT_ERROR: UserFacingError = UserFacingError(
    error_code="ERR_UNKNOWN_001",
    message="Algo inesperado aconteceu.",
    suggestions=["Tente novamente em alguns instantes."],
    recovery_actions=[
        RecoveryAction(label="Tentar novamente", callback_data="retry:last_action"),
        RecoveryAction(label="Cancelar", callback_data="action:cancel")
    ],
    severity=ErrorSeverity.ERROR
)
```

## Error Code Format

**Pattern**: `ERR_{DOMAIN}_{NUMBER}`

| Domain | Description | Number Range |
|--------|-------------|--------------|
| STORAGE | File system, disk space | 001-099 |
| NETWORK | Connectivity, timeout | 100-199 |
| TRANSCRIPTION | Whisper, audio processing | 200-299 |
| SESSION | Session lifecycle, conflicts | 300-399 |
| TELEGRAM | API limits, message delivery | 400-499 |
| CONFIG | Missing config, invalid values | 500-599 |
| UNKNOWN | Unmapped exceptions | 900-999 |

## Minimum Required Entries

The following error codes MUST be defined for MVP:

### Storage Errors

| Code | Exception Mapping | User Message |
|------|-------------------|--------------|
| ERR_STORAGE_001 | `PermissionError` | "Não foi possível salvar o áudio no momento." |
| ERR_STORAGE_002 | `OSError` (disk full) | "O espaço de armazenamento está esgotado." |

### Network Errors

| Code | Exception Mapping | User Message |
|------|-------------------|--------------|
| ERR_NETWORK_001 | `TimeoutError` | "A operação demorou mais que o esperado." |
| ERR_NETWORK_002 | `ConnectionError` | "Não foi possível conectar ao serviço." |

### Transcription Errors

| Code | Exception Mapping | User Message |
|------|-------------------|--------------|
| ERR_TRANSCRIPTION_001 | `RuntimeError` (Whisper) | "Não foi possível transcrever o áudio." |
| ERR_TRANSCRIPTION_002 | N/A (empty audio) | "O áudio parece estar vazio ou sem fala detectável." |

### Session Errors

| Code | Exception Mapping | User Message |
|------|-------------------|--------------|
| ERR_SESSION_001 | `ValueError` (no session) | "Nenhuma sessão ativa encontrada." |
| ERR_SESSION_002 | N/A (conflict) | "Já existe uma sessão em andamento." |
| ERR_SESSION_003 | N/A (orphaned) | "Sessão anterior não foi finalizada corretamente." |

### Telegram Errors

| Code | Exception Mapping | User Message |
|------|-------------------|--------------|
| ERR_TELEGRAM_001 | `telegram.error.BadRequest` | "Não foi possível enviar a mensagem." |
| ERR_TELEGRAM_002 | N/A (rate limit) | "Muitas mensagens em sequência. Aguarde um momento." |

## Recovery Actions

Standard recovery action patterns:

| Action | callback_data | Description |
|--------|---------------|-------------|
| Retry | `retry:{operation}` | Retry the failed operation |
| Cancel | `action:cancel` | Cancel current operation |
| Help | `action:help` | Show contextual help |
| Ignore | `action:dismiss` | Dismiss error and continue |
| Resume | `action:resume_session` | Resume orphaned session |
| Finalize | `action:finalize_orphan` | Finalize orphaned session |

## Contract Tests

**Location**: `tests/contract/test_error_catalog.py`

```python
def test_all_required_codes_present():
    """Verify all minimum required error codes exist."""
    required = [
        "ERR_STORAGE_001", "ERR_STORAGE_002",
        "ERR_NETWORK_001", "ERR_NETWORK_002",
        "ERR_TRANSCRIPTION_001", "ERR_TRANSCRIPTION_002",
        "ERR_SESSION_001", "ERR_SESSION_002", "ERR_SESSION_003",
        "ERR_TELEGRAM_001", "ERR_TELEGRAM_002",
    ]
    for code in required:
        assert code in ERROR_CATALOG, f"Missing required error: {code}"

def test_all_errors_have_recovery_actions():
    """Every error must have at least one recovery action."""
    for code, error in ERROR_CATALOG.items():
        assert len(error.recovery_actions) >= 1, f"{code} has no recovery actions"

def test_no_technical_jargon_in_messages():
    """Messages must not contain technical terms."""
    forbidden = ["exception", "stack", "trace", "null", "error code", "runtime"]
    for code, error in ERROR_CATALOG.items():
        msg_lower = error.message.lower()
        for term in forbidden:
            assert term not in msg_lower, f"{code} contains forbidden term: {term}"

def test_default_error_exists():
    """DEFAULT_ERROR must be defined for unmapped exceptions."""
    assert DEFAULT_ERROR is not None
    assert DEFAULT_ERROR.error_code.startswith("ERR_UNKNOWN")
```

## Integration with ErrorPresentationLayer

```python
# In src/services/presentation/error_handler.py

from src.lib.error_catalog import ERROR_CATALOG, DEFAULT_ERROR

class ErrorPresentationLayer:
    def get_error_by_code(self, error_code: str) -> UserFacingError:
        return ERROR_CATALOG.get(error_code, DEFAULT_ERROR)
```

## Notes

- All messages are in Portuguese (pt-BR) as default language
- Future localization: messages moved to JSON/YAML config files with language keys
- Error severity determines UI treatment (color, icon, sound if applicable)
- Recovery actions must map to existing CallbackQueryHandler patterns
````
