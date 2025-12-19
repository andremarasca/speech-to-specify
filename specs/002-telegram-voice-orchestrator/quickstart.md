# Quickstart: Telegram Voice Orchestrator (OATL)

**Feature Branch**: `002-telegram-voice-orchestrator`  
**Purpose**: Get the voice orchestrator daemon running locally

## Prerequisites

### Hardware
- NVIDIA GPU with CUDA support (tested: RTX 3050, 4GB VRAM)
- 32GB RAM recommended
- SSD with 10GB+ free space for models and sessions

### Software
- Windows 11
- Python 3.11+
- CUDA 12.x toolkit installed
- ffmpeg in PATH

### Telegram
- Telegram account
- Bot token from [@BotFather](https://t.me/BotFather)
- Your chat ID (use [@userinfobot](https://t.me/userinfobot) to find it)

## Installation

### 1. Clone and Setup Environment

```powershell
cd C:\Projects\speech-to-specify
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Install Whisper Dependencies

```powershell
# PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verify CUDA
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Whisper
pip install openai-whisper

# Download model (first run will download ~500MB)
python -c "import whisper; whisper.load_model('small.en')"
```

### 3. Install Telegram Bot Library

```powershell
pip install python-telegram-bot[all]
```

### 4. Configure Environment

Create `.env` file in project root:

```env
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_CHAT_ID=your_chat_id

# Whisper Configuration
WHISPER_MODEL=small.en
WHISPER_DEVICE=cuda

# Session Storage
SESSIONS_DIR=./sessions

# LLM Provider (for downstream processing)
DEFAULT_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
```

## Running the Daemon

### Start the Voice Orchestrator

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run daemon
python -m src.cli.daemon
```

Expected output:
```
[2025-12-18 14:30:00] INFO: Loading Whisper model (small.en)...
[2025-12-18 14:30:15] INFO: Model loaded on cuda
[2025-12-18 14:30:15] INFO: Starting Telegram bot...
[2025-12-18 14:30:16] INFO: Bot connected. Listening for messages...
```

### Verify Bot is Working

1. Open Telegram
2. Find your bot (search by username you created with BotFather)
3. Send `/status`
4. Should receive: "✅ Orchestrator running. No active session."

## Usage Workflow

### 1. Start a Session

```
/start
```
Response: "📂 Session 2025-12-18_14-30-00 created. Send voice messages."

### 2. Send Voice Messages

Record and send voice messages in Telegram. Each one is downloaded and stored.

Response per audio: "🎤 Audio 1 received (45 seconds)"

### 3. Finalize and Transcribe

```
/finish
```
Response: "⏳ Transcribing 3 audio files..."

Wait for transcription to complete:
"✅ Transcription complete. 3/3 files processed."

### 4. Review Transcripts

```
/transcripts
```
Returns transcribed text via Telegram.

### 5. Process with Narrative Pipeline

```
/process
```
Response: "🔄 Processing session with narrative pipeline..."

Wait for processing:
"✅ Processing complete. Use /list to see results."

### 6. Retrieve Results

```
/list
```
Shows available files in session.

```
/get 02_specification.md
```
Sends specific file via Telegram.

## Troubleshooting

### "CUDA not available"

```powershell
# Verify CUDA installation
nvidia-smi

# Verify PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

If False, reinstall PyTorch with correct CUDA version.

### "Bot token invalid"

1. Check token in .env (no quotes needed)
2. Verify token with BotFather
3. Make sure bot hasn't been revoked

### "Unauthorized access"

1. Verify `TELEGRAM_ALLOWED_CHAT_ID` matches your chat ID
2. Use @userinfobot to get correct ID

### "Transcription failed"

Check audio format is supported (ogg, mp3, wav). If issue persists, check:

```powershell
ffmpeg -version  # Must be in PATH
```

## Session Files Location

After workflow completes, session data is at:

```
sessions/
└── 2025-12-18_14-30-00/
    ├── metadata.json
    ├── audio/
    ├── transcripts/
    └── process/
        └── output/
            └── executions/
                └── {timestamp}/
                    └── artifacts/
```

All files are human-readable and can be inspected directly.

## Stopping the Daemon

Press `Ctrl+C` in the terminal running the daemon.

The daemon saves state and shuts down gracefully. In-progress transcriptions will complete before exit.
