# Quickstart: Auto-Session Audio Capture

**Feature**: 003-auto-session-audio  
**Prerequisites**: Python 3.11+, Telegram Bot configured

## Setup

### 1. Install Dependencies

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install new dependencies
pip install sentence-transformers>=2.2.0
```

### 2. Configure Environment

Ensure `.env` has:
```env
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ALLOWED_CHAT_ID=your-chat-id
```

### 3. First Run (Downloads Model)

The first semantic search will download the embedding model (~90MB):
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

## Testing the Feature

### Test 1: Auto-Session Creation (P1)

**Goal**: Verify audio creates session automatically

1. **Ensure no active session**:
   ```
   /status
   ```
   Expected: "No active session"

2. **Send voice message** (any content)

3. **Verify response**:
   - ✅ Message confirms session created
   - ✅ Message includes session name (e.g., "Áudio de 18 de Dezembro")
   - ✅ Message confirms audio received

4. **Verify session exists**:
   ```
   /status
   ```
   Expected: Shows active session with audio count

### Test 2: Intelligible Names (P2)

**Goal**: Verify session names update from content

1. **Create session with audio** (speak clearly, e.g., "This is about the monthly sales report")

2. **Finalize and transcribe**:
   ```
   /done
   ```

3. **Wait for transcription** (~10-30 seconds)

4. **List sessions**:
   ```
   /list
   ```
   Expected: Session name changed from "Áudio de..." to content-based name

### Test 3: Natural Language Reference (P3)

**Goal**: Verify session lookup by description

1. **Create multiple sessions** with different content:
   - Session 1: Audio about "project planning"
   - Session 2: Audio about "monthly report"

2. **Process both sessions** (finalize, transcribe)

3. **Reference by description**:
   ```
   /session monthly
   ```
   Expected: Shows session matching "monthly report"

4. **Test ambiguity**:
   ```
   /session report
   ```
   Expected: If both match, shows candidates for selection

### Test 4: Context Commands (P3)

**Goal**: Verify commands use active session

1. **Create a session and add audio**:
   - Send voice message
   - Verify session created

2. **Request transcription without specifying session**:
   ```
   /transcripts
   ```
   Expected: Uses active session (or prompts if none active)

3. **Request status without specifying session**:
   ```
   /status
   ```
   Expected: Shows active session details

## Validation Checklist

| Test | Expected | Pass? |
|------|----------|-------|
| Audio without session → creates session | ✅ | ☐ |
| Created session has fallback name | ✅ | ☐ |
| User receives confirmation with name | ✅ | ☐ |
| Session name updates after transcription | ✅ | ☐ |
| `/list` shows intelligible names | ✅ | ☐ |
| `/session <name>` finds session | ✅ | ☐ |
| Ambiguous reference shows candidates | ✅ | ☐ |
| `/transcripts` uses active session | ✅ | ☐ |
| `/status` uses active session | ✅ | ☐ |

## Troubleshooting

### "No matching session found"

- Check session name with `/list`
- Try more specific reference
- Semantic matching requires embedding model loaded

### Slow first semantic search

- First query loads model (~5s)
- Subsequent queries are fast (~50ms)

### Name not updating from transcription

- Check transcription completed: `/status`
- Name only updates if current source is `FALLBACK_TIMESTAMP`
- Check logs for extraction errors

## Running Tests

```bash
# Unit tests for NameGenerator
pytest tests/unit/test_name_generator.py -v

# Unit tests for SessionMatcher  
pytest tests/unit/test_session_matcher.py -v

# Contract tests
pytest tests/contract/test_session_matcher.py -v
pytest tests/contract/test_name_generator.py -v
pytest tests/contract/test_auto_session_handler.py -v

# Integration tests
pytest tests/integration/test_auto_session.py -v

# All tests
pytest tests/ -v --tb=short
```
