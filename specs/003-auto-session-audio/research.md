# Research: Auto-Session Audio Capture

**Feature**: 003-auto-session-audio  
**Date**: 2025-12-18  
**Status**: Complete

## Research Tasks

### 1. Session Name Generation Strategy

**Question**: How to generate intelligible session names from audio content?

**Decision**: Cascading fallback strategy with three tiers

**Rationale**: Audio content is not immediately available as text. Names must be generated progressively as processing completes, with immediate fallbacks for responsiveness.

**Implementation**:
1. **Immediate (T+0s)**: Timestamp-based fallback in Portuguese locale
   - Format: "Áudio de {day} de {month}" (e.g., "Áudio de 18 de Dezembro")
   - Uniqueness ensured by appending sequence number if collision
2. **After transcription (T+~10s)**: First meaningful words from transcript
   - Extract first 3-5 words, excluding filler words
   - Truncate at sentence boundary if possible
3. **After LLM processing (T+~30s)**: Title extracted by constitution/spec steps
   - Use artifact output if it contains explicit title

**Alternatives Considered**:
- **UUID-based**: Rejected (violates "intelligible identifiers" principle)
- **User-prompted naming**: Rejected (adds friction, violates "natural interaction")
- **Audio fingerprint hash**: Rejected (not human-readable)

---

### 2. Natural Language Session Matching

**Question**: How to match user references like "the monthly report session" to actual sessions?

**Decision**: Hybrid substring + semantic similarity matching

**Rationale**: Users reference sessions in varied ways—sometimes exact name fragments, sometimes semantic descriptions. A hybrid approach handles both cases.

**Implementation**:
1. **Tier 1: Exact substring match**
   - Case-insensitive search in session `intelligible_name`
   - If single match found, return immediately (confidence: 1.0)
   
2. **Tier 2: Fuzzy substring match**
   - Levenshtein distance with threshold (≤2 edits)
   - Handles typos in session references
   
3. **Tier 3: Semantic similarity**
   - Generate embedding for user reference text
   - Compare against pre-computed session embeddings
   - Return matches above similarity threshold (>0.7)

**Confidence scoring**:
- Exact substring: 1.0
- Fuzzy substring: 0.9
- Semantic similarity: raw cosine similarity score

**Ambiguity handling**:
- If multiple matches with confidence >0.7, present candidates to user
- If no matches above 0.5, inform user "no matching session found"

**Alternatives Considered**:
- **Semantic-only**: Rejected (overkill for exact name fragments, slower)
- **Substring-only**: Rejected (fails for paraphrased references)
- **LLM-based matching**: Rejected (violates local-only processing constraint)

---

### 3. Sentence-Transformers Integration Pattern

**Question**: How to integrate sentence-transformers for local semantic matching?

**Decision**: Use `sentence-transformers/all-MiniLM-L6-v2` with lazy loading

**Rationale**: This model offers best balance of quality vs. size for CPU inference. Lazy loading avoids startup penalty when semantic matching isn't needed.

**Implementation**:
```python
# Lazy-loaded singleton pattern
class EmbeddingService:
    _model = None
    
    @classmethod
    def get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer('all-MiniLM-L6-v2')
        return cls._model
    
    @classmethod
    def embed(cls, text: str) -> list[float]:
        return cls.get_model().encode(text).tolist()
```

**Model choice**:
- `all-MiniLM-L6-v2`: 22M params, 80MB, ~5ms/embedding on CPU
- Alternative `all-mpnet-base-v2`: Better quality but 110M params, 420MB

**Storage of embeddings**:
- Store in session metadata JSON as `embedding: list[float]`
- Recompute on session name change
- Lazy computation: only generate when first semantic search requested

**Alternatives Considered**:
- **all-mpnet-base-v2**: Rejected (too large for startup, marginal quality gain)
- **OpenAI embeddings**: Rejected (violates local-only constraint)
- **TF-IDF**: Rejected (poor semantic quality for short phrases)

---

### 4. Auto-Session Creation Flow

**Question**: How to handle audio receipt when no session exists?

**Decision**: Atomic persist-then-create pattern

**Rationale**: Audio must never be lost. Persist raw audio first, then create session context. This ensures data survival even if session creation fails.

**Implementation flow**:
```
1. Audio received from Telegram
2. PERSIST audio bytes to temp location (guaranteed durable)
3. CHECK for active session
4. IF no active session:
   a. CREATE session with fallback name
   b. MOVE audio to session folder
   c. LINK audio entry to session
5. ELSE:
   a. LINK audio to existing active session
6. CONFIRM receipt to user (includes session name)
7. ENQUEUE transcription job (async)
```

**Failure modes**:
- Persist fails: Return error to user, retry message
- Session creation fails: Audio is safe in temp, manual recovery possible
- Transcription fails: Session exists, name remains fallback, retry allowed

**Alternatives Considered**:
- **Create session first**: Rejected (audio could be lost if creation fails)
- **Transactional database**: Rejected (overkill for single-user, adds complexity)

---

### 5. Session State Extensions

**Question**: What fields need to be added to Session model?

**Decision**: Add `intelligible_name`, `name_source`, and `embedding` fields

**New fields**:
```python
@dataclass
class Session:
    # ... existing fields ...
    
    # NEW: Human-readable name for the session
    intelligible_name: str  # e.g., "Áudio de 18 de Dezembro" or "relatório mensal"
    
    # NEW: Source of the name (for debugging/auditing)
    name_source: NameSource  # FALLBACK_TIMESTAMP | TRANSCRIPTION | LLM_TITLE | USER_ASSIGNED
    
    # NEW: Semantic embedding for matching (optional, computed lazily)
    embedding: Optional[list[float]] = None
```

**Name lifecycle**:
1. Session created → `name_source=FALLBACK_TIMESTAMP`
2. Transcription completes → Update name, `name_source=TRANSCRIPTION`
3. LLM extracts title → Update name, `name_source=LLM_TITLE`
4. User renames → Update name, `name_source=USER_ASSIGNED`

---

## Dependencies to Add

```txt
# requirements.txt additions
sentence-transformers>=2.2.0  # For semantic embeddings
```

**Note**: sentence-transformers pulls in torch if not already present. The project already has `torch>=2.1.0` for whisper, so no additional weight.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Embedding model download on first use | Medium | Pre-download in setup script, cache in `.cache/` |
| Slow semantic matching with many sessions | Low (scale: ~100) | Index-based filtering, short-circuit on exact match |
| Name collisions | Low | Sequence suffix for duplicates |
| Portuguese locale formatting | Low | Use `babel` library for locale-aware dates |
