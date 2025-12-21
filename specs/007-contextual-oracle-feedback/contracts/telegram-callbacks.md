# Contract: Telegram Callbacks (Oracle Feedback)

**Component**: `src/services/telegram/keyboards.py` (extend), `src/cli/daemon.py` (extend)  
**Purpose**: Handle oracle selection via inline keyboard buttons

## Keyboard Interface

```python
from telegram import InlineKeyboardMarkup
from src.models.oracle import Oracle

def build_oracle_keyboard(
    oracles: list[Oracle],
    simplified: bool = False,
) -> InlineKeyboardMarkup:
    """
    Build inline keyboard with oracle buttons.
    
    Args:
        oracles: List of available oracles
        simplified: Use simplified button labels (no emojis)
        
    Returns:
        InlineKeyboardMarkup with one button per oracle
    """
```

## Callback Data Format

```text
oracle:{oracle_id}
```

**Example**: `oracle:a1b2c3d4`

**Constraints**:
- Total callback_data must be ≤ 64 bytes
- `oracle:` prefix = 7 bytes
- `oracle_id` = 8 bytes
- Total = 15 bytes (well under limit)

## Button Layout

```text
┌────────────────────────────────┐
│ 🎭 Cético                      │
├────────────────────────────────┤
│ 🔮 Visionário                  │
├────────────────────────────────┤
│ ☀️ Otimista                    │
└────────────────────────────────┘
```

**Simplified mode** (no emojis):
```text
┌────────────────────────────────┐
│ Cético                         │
├────────────────────────────────┤
│ Visionário                     │
├────────────────────────────────┤
│ Otimista                       │
└────────────────────────────────┘
```

## Callback Handler Interface

```python
async def handle_oracle_callback(
    event: TelegramEvent,
    oracle_id: str,
    session: Session,
) -> None:
    """
    Handle oracle button click.
    
    1. Validate session has transcripts
    2. Load oracle by ID
    3. Build context from session
    4. Send typing indicator
    5. Request LLM response
    6. Persist response to session
    7. Send response to user
    8. Update keyboard with new state
    """
```

## Behavior Contracts

### BC-TC-001: Oracle Keyboard After Transcription

**Given** a transcription is completed for active session  
**When** transcription message is sent to user  
**Then** oracle keyboard is attached below the message

### BC-TC-002: No Oracles Available

**Given** oracles directory is empty  
**When** transcription completes  
**Then** message indicates no oracles available, no keyboard attached

### BC-TC-003: Oracle Button Click - Success

**Given** active session with transcripts  
**When** user clicks oracle button  
**Then** typing indicator shown, LLM called, response displayed

### BC-TC-004: Oracle Button Click - No Transcripts

**Given** active session with zero transcripts  
**When** user clicks oracle button  
**Then** informative message: "Envie um áudio primeiro para receber feedback."

### BC-TC-005: Oracle Button Click - Invalid Oracle ID

**Given** oracle was deleted after keyboard was displayed  
**When** user clicks stale oracle button  
**Then** error message: "Oráculo não encontrado. Tente novamente."

### BC-TC-006: Typing Indicator During LLM Request

**Given** user clicks oracle button  
**When** LLM request is in progress  
**Then** Telegram "typing" action is sent every 5 seconds until response

### BC-TC-007: LLM Timeout Handling

**Given** LLM request exceeds 30 second timeout  
**When** timeout occurs  
**Then** user message: "Tempo esgotado. Tente novamente." with retry button

### BC-TC-008: LLM Error Handling

**Given** LLM returns error (not timeout)  
**When** error occurs  
**Then** user message with error summary and retry button

### BC-TC-009: Response Persistence

**Given** LLM returns successful response  
**When** response is displayed to user  
**Then** response is saved to `llm_responses/` and LlmEntry added to session

### BC-TC-010: Keyboard Refresh After Response

**Given** oracle response is successfully displayed  
**When** message is sent  
**Then** oracle keyboard is attached for follow-up interactions

### BC-TC-011: Toggle LLM History Button

**Given** active session with oracle keyboard displayed  
**When** toggle button is clicked  
**Then** `include_llm_history` preference is toggled, confirmation message sent

### BC-TC-012: Button Label Reflects Toggle State

**Given** `include_llm_history=True`  
**When** oracle keyboard is built  
**Then** toggle button shows "🔗 Histórico: ON"

**Given** `include_llm_history=False`  
**When** oracle keyboard is built  
**Then** toggle button shows "🔗 Histórico: OFF"

### BC-TC-013: Volatile Memory Mode Alert

**Given** persistence subsystem fails (e.g., disk write error)  
**When** user sends audio or requests oracle feedback  
**Then** message includes visible alert: "⚠️ Modo memória volátil - respostas não serão salvas"

## Callback Data Registry

| Pattern | Handler | Description |
|---------|---------|-------------|
| `oracle:{id}` | `handle_oracle_callback` | Request feedback from oracle |
| `toggle:llm_history` | `handle_toggle_llm_history` | Toggle include_llm_history preference |
| `retry:oracle:{id}` | `handle_oracle_callback` | Retry failed oracle request |

## Error Messages

| Condition | Message |
|-----------|---------|
| No transcripts | "📝 Envie um áudio primeiro para receber feedback." |
| Oracle not found | "❌ Oráculo não encontrado. A lista foi atualizada." |
| LLM timeout | "⏱️ Tempo esgotado ao aguardar resposta. Tente novamente." |
| LLM error | "⚠️ Erro ao obter feedback: {error_summary}" |
| No oracles available | "🎭 Nenhum oráculo disponível. Adicione arquivos em {oracles_dir}." |
| Volatile memory mode | "⚠️ Modo memória volátil ativo - histórico não será persistido." |

## Test Requirements

- Unit tests for keyboard building with various oracle counts
- Unit tests for callback data format generation/parsing
- Contract tests for all BC-TC-* behaviors
- Integration tests for full oracle feedback flow
