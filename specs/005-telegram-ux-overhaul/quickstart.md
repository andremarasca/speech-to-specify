# Quickstart: Telegram UX Overhaul

**Feature**: 005-telegram-ux-overhaul  
**Date**: 2025-12-19

## Prerequisites

- Python 3.11+ installed
- Git repository cloned
- Virtual environment activated
- Telegram bot token (from @BotFather)
- Your Telegram chat ID

## Setup Steps

### 1. Environment Setup

```bash
# Clone and enter directory (if not already done)
cd speech-to-specify

# Create/activate virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Unix/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create `.env` file with required settings:

```bash
# Copy example if exists
cp .env.example .env
```

Required environment variables:

```ini
# Telegram Bot Configuration (REQUIRED)
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
TELEGRAM_ALLOWED_CHAT_ID=your-telegram-chat-id

# LLM Provider (for artifact pipeline)
NARRATE_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key

# Optional: Whisper Configuration
WHISPER_MODEL=small.en
WHISPER_DEVICE=cuda  # or 'cpu' if no GPU
```

### 3. Verify Installation

```bash
# Run tests to verify setup
pytest tests/contract/ -v

# Check Telegram configuration
python -c "from src.lib.config import get_telegram_config; c = get_telegram_config(); print(f'Configured: {c.is_configured()}')"
```

### 4. Start the Bot

```bash
# Run the Telegram daemon
python -m src.cli.daemon
```

## Validation Checklist

After implementation, verify these work:

### Zero-Command Flow (User Story 1)
- [ ] Send voice message to bot with no active session
- [ ] Verify session auto-created with confirmation message
- [ ] Verify inline keyboard appears (Finalize, Status, Help)
- [ ] Send second voice message
- [ ] Verify "Audio 2 received" acknowledgment
- [ ] Tap "Finalize" button
- [ ] Verify transcription completes

### Progress Feedback (User Story 2)
- [ ] During transcription, verify progress message appears
- [ ] Verify progress updates at least 3 times
- [ ] Verify progress shows percentage and description

### Error Recovery (User Story 3)
- [ ] Simulate error (e.g., fill disk, disconnect network)
- [ ] Verify error message is human-readable
- [ ] Verify recovery buttons appear
- [ ] Verify tapping recovery button works

### Session Conflict (User Story 4)
- [ ] With active session, send `/start` command
- [ ] Verify confirmation dialog appears
- [ ] Verify options work correctly

### Backward Compatibility
- [ ] Verify `/start` command still works
- [ ] Verify `/done` command still works
- [ ] Verify `/status` command still works
- [ ] Verify `/help` command still works

## Development Commands

```bash
# Run all tests
pytest

# Run contract tests only
pytest tests/contract/ -v

# Run integration tests
pytest tests/integration/ -v

# Run with coverage
pytest --cov=src --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
```

## File Locations

| Purpose | Location |
|---------|----------|
| UI Service | `src/services/telegram/ui_service.py` |
| Keyboard Builders | `src/services/telegram/keyboards.py` |
| Error Handler | `src/services/presentation/error_handler.py` |
| Progress Reporter | `src/services/presentation/progress.py` |
| UI State Models | `src/models/ui_state.py` |
| Message Templates | `src/lib/messages.py` |
| UI Config | `src/lib/config.py` (UIConfig class) |
| Contract Tests | `tests/contract/test_ui_*.py` |
| Integration Tests | `tests/integration/test_inline_keyboard_flow.py` |

## Troubleshooting

### Bot not responding
1. Check `TELEGRAM_BOT_TOKEN` is valid
2. Check `TELEGRAM_ALLOWED_CHAT_ID` matches your chat
3. Check bot is running: `python -m src.cli.daemon`
4. Check logs for errors

### Inline keyboards not appearing
1. Verify python-telegram-bot version >= 22.0
2. Check `CallbackQueryHandler` is registered in bot.py
3. Enable verbose logging: `NARRATE_VERBOSE=true`

### Progress not updating
1. Check `UI_PROGRESS_INTERVAL_SECONDS` configuration
2. Verify ProgressReporter is receiving updates from transcription service
3. Check for Telegram API rate limiting errors in logs

### Tests failing
1. Run `pytest tests/contract/ -v --tb=short` for detailed output
2. Check mock fixtures are configured correctly
3. Verify all dependencies installed: `pip install -r requirements-dev.txt`

## Success Metrics Validation

After deployment, measure:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Time to first transcription | < 2 minutes | Log timestamps from session start to transcription complete |
| Interactions per session | ≤ 3 | Count button taps + commands per session |
| Abandonment rate | < 10% | Sessions created vs sessions finalized |
| Error recovery rate | > 90% | User actions after error vs error count |
| Help command usage | < 20% | `/help` invocations per session |
