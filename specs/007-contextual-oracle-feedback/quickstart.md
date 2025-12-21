# Quickstart: Contextual Oracle Feedback

**Feature**: 007-contextual-oracle-feedback  
**Time to First Value**: ~15 minutes

## Prerequisites

- Python 3.11+ installed
- Telegram bot token configured (`TELEGRAM_BOT_TOKEN`)
- LLM API key configured (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`)
- Active session capability (existing system running)

## Step 1: Create Oracles Directory

```bash
mkdir -p prompts/oracles
```

## Step 2: Create Your First Oracle

Create `prompts/oracles/cetico.md`:

```markdown
# Cético

Você é um pensador cético e rigoroso. Seu papel é desafiar as ideias apresentadas.

## Contexto do Usuário

{{CONTEXT}}

## Instruções

Analise o contexto e forneça feedback crítico:
1. Identifique premissas questionáveis
2. Aponte lacunas no raciocínio
3. Sugira refinamentos
```

## Step 3: Configure Environment

Add to `.env`:

```bash
# Oracle Configuration
ORACLES_DIR=prompts/oracles
ORACLE_PLACEHOLDER={{CONTEXT}}
ORACLE_CACHE_TTL=10
LLM_TIMEOUT_SECONDS=30
```

## Step 4: Start the Bot

```bash
python -m src.cli.daemon
```

## Step 5: Test the Flow

1. **Send a voice message** to your Telegram bot
2. **Wait for transcription** to complete
3. **Look for oracle buttons** below the transcription
4. **Click "Cético"** to request feedback
5. **View the response** with context from your audio

## Adding More Oracles

Simply add more `.md` files to `prompts/oracles/`:

```bash
# Create visionario.md
cat > prompts/oracles/visionario.md << 'EOF'
# Visionário

Você é um pensador visionário e otimista. Expanda as ideias apresentadas.

{{CONTEXT}}

Sugira possibilidades e conexões inesperadas.
EOF
```

The new oracle appears automatically on the next interaction (no restart needed).

## Verification Checklist

- [ ] Oracle buttons appear after transcription
- [ ] Clicking oracle shows "typing..." indicator
- [ ] Response is displayed within 30 seconds
- [ ] Response references content from your audio
- [ ] New oracle files appear as buttons automatically
- [ ] Toggle button changes between "Histórico: ON/OFF"

## Troubleshooting

### No oracle buttons appear

1. Check `ORACLES_DIR` is set correctly
2. Verify at least one `.md` file exists in the directory
3. Check logs for "No oracles found" warning

### Oracle returns error

1. Check LLM API key is configured
2. Verify `LLM_TIMEOUT_SECONDS` is sufficient
3. Check logs for specific error message

### New oracle not appearing

1. Wait for cache to expire (default 10 seconds)
2. Send a new audio to trigger refresh
3. Check file has valid markdown H1 title

## Next Steps

- Read [Tutorial: Adding Oracles](../../docs/tutorial_adding_oracles.md) for advanced customization
- Read [Tutorial: Context Management](../../docs/tutorial_context_management.md) for history toggle details
