# Research: Contextual Oracle Feedback

**Feature**: 007-contextual-oracle-feedback  
**Date**: 2025-12-20  
**Status**: Complete

## Research Tasks

### 1. Oracle File Format and Parsing

**Question**: What is the best approach for parsing markdown oracle files?

**Decision**: Simple first-line extraction with regex, fallback to filename

**Rationale**:
- Oracle files are simple markdown with title in first line (`# Title`)
- Complex markdown parsing (AST) is overkill for this use case
- Regex `^#\s*(.+)$` reliably extracts H1 titles
- Fallback to filename (sans extension) ensures graceful degradation

**Alternatives Considered**:
- Full markdown parser (e.g., mistune) — Rejected: unnecessary dependency for single-line extraction
- YAML frontmatter — Rejected: adds complexity, not aligned with "arquivo markdown simples" requirement

### 2. Context Concatenation Strategy

**Question**: How to concatenate transcripts and LLM responses for context?

**Decision**: Linear chronological concatenation with clear delimiters

**Rationale**:
- Spec requires chronological order (FR-008)
- Clear origin identification needed (FR-009)
- Simple format allows LLMs to understand structure

**Format**:
```text
[TRANSCRIÇÃO 1 - 2025-12-20 10:30:00]
{transcript content}

[ORÁCULO: Cético - 2025-12-20 10:32:15]
{llm response}

[TRANSCRIÇÃO 2 - 2025-12-20 10:35:00]
{transcript content}
```

**Alternatives Considered**:
- JSON structure — Rejected: LLMs handle plain text better for creative tasks
- XML-style tags — Rejected: More verbose, no clear benefit

### 3. Oracle Directory Monitoring

**Question**: How to detect new oracle files without restart?

**Decision**: Lazy loading with short TTL cache (10 seconds)

**Rationale**:
- File system watchers (watchdog) add complexity and dependencies
- SC-003 requires new oracles to appear "na próxima interação"
- TTL cache balances freshness with performance
- Consistent with "Pure stdlib" principle where possible

**Implementation**:
```python
class OracleManager:
    _cache: dict[str, Oracle] = {}
    _cache_expiry: datetime = datetime.min
    CACHE_TTL_SECONDS = 10
    
    def list_oracles(self) -> list[Oracle]:
        if datetime.now() > self._cache_expiry:
            self._reload_cache()
        return list(self._cache.values())
```

**Alternatives Considered**:
- watchdog file watcher — Rejected: External dependency, complexity for simple use case
- No caching (scan every request) — Rejected: Performance concern for rapid interactions

### 4. Telegram callback_data Limit (64 bytes)

**Question**: How to handle oracle identifiers within 64-byte limit?

**Decision**: Use short hash-based identifiers

**Rationale**:
- Telegram limits callback_data to 64 bytes
- Format: `oracle:{short_id}` where short_id is 8-char hash
- Example: `oracle:a1b2c3d4` = 15 bytes, well under limit
- Lookup table maps short_id to full oracle path

**Implementation**:
```python
def generate_oracle_id(file_path: Path) -> str:
    """Generate 8-char hash from file path."""
    return hashlib.sha256(str(file_path).encode()).hexdigest()[:8]
```

**Alternatives Considered**:
- Full filename in callback — Rejected: Easily exceeds 64 bytes
- Numeric indices — Rejected: Changes when files added/removed

### 5. LLM Response Persistence Format

**Question**: How to structure LLM response storage in session?

**Decision**: Extend existing session pattern with `llm_responses/` subfolder

**Rationale**:
- Consistent with existing `audio/` and `transcripts/` structure
- JSON metadata in Session model (like AudioEntry)
- Text files for response content (readable, auditable)

**File Structure**:
```text
sessions/{session_id}/
├── metadata.json           # Session model with llm_entries
├── audio/
├── transcripts/
└── llm_responses/          # NEW
    ├── 001_cetico.txt      # {sequence}_{oracle_name}.txt
    └── 002_visionario.txt
```

**LlmEntry in metadata.json**:
```json
{
  "sequence": 1,
  "oracle_name": "Cético",
  "oracle_id": "a1b2c3d4",
  "created_at": "2025-12-20T10:32:15Z",
  "response_filename": "001_cetico.txt",
  "context_snapshot": {
    "transcript_count": 3,
    "llm_response_count": 0,
    "include_llm_history": true
  }
}
```

### 6. Toggle de Histórico LLM

**Question**: How to implement the include_llm_history toggle?

**Decision**: Session-level preference stored in Session.ui_preferences

**Rationale**:
- Existing `ui_preferences` field in Session model (UIPreferences dataclass)
- Consistent with existing preference storage pattern
- Toggle via Telegram button (KeyboardType.SETTINGS or inline toggle)

**Implementation**:
- Add `include_llm_history: bool = True` to UIPreferences
- Toggle callback: `toggle:llm_history`
- Context builder reads preference from active session

### 7. Error Handling and Resilience

**Question**: How to handle LLM timeouts and failures gracefully?

**Decision**: Isolated error handling with user notification

**Rationale**:
- Spec requires isolation of input/output errors (US5)
- LLM failures must not corrupt session state
- User must be informed but allowed to retry

**Implementation**:
```python
async def request_oracle_feedback(session: Session, oracle: Oracle) -> OracleResult:
    try:
        context = build_context(session)
        response = await llm_client.complete(oracle.prompt, context, timeout=30)
        entry = persist_response(session, oracle, response)
        return OracleResult.success(entry)
    except TimeoutError:
        log.warning(f"Oracle {oracle.name} timeout for session {session.id}")
        return OracleResult.timeout(oracle.name)
    except LLMError as e:
        log.error(f"Oracle {oracle.name} error: {e}")
        return OracleResult.error(oracle.name, str(e))
```

## Dependencies Identified

| Dependency | Purpose | Status |
|------------|---------|--------|
| Existing Session model | Extend with LlmEntry | Extend |
| Existing keyboards.py | Add oracle keyboard builder | Extend |
| Existing config.py | Add OracleConfig | Extend |
| prompts/oracles/ directory | Oracle personality files | Create |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM response too slow | Medium | User frustration | 30s timeout with visual feedback ("digitando...") |
| Oracle file corruption | Low | Missing button | Graceful skip with warning log |
| Context too large for LLM | Medium | Truncation/error | Token counting and summarization strategy |
| callback_data collision | Very Low | Wrong oracle | SHA256 hash collision is negligible |

## Conclusion

All technical questions resolved. No NEEDS CLARIFICATION items remain. Ready to proceed to Phase 1: Design & Contracts.
