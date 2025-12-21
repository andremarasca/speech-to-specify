# Tutorial: Context Management for Oracle Feedback

This guide explains how context is built and managed for oracle feedback requests.

## Overview

When you click an oracle button after transcription, the system builds a "context" containing your session's content. This context is injected into the oracle's prompt so it can provide relevant, contextual feedback.

## Context Components

### 1. Transcripts

All transcribed audio from your current session, ordered chronologically:

```
[TRANSCRIÇÃO 1 - 2025-12-20 10:30:15]
First audio content here...

[TRANSCRIÇÃO 2 - 2025-12-20 10:35:22]
Second audio content here...
```

### 2. LLM Responses (Optional)

Previous oracle feedback, if "LLM History" is enabled:

```
[ORÁCULO: Cético - 2025-12-20 10:32:00]
Previous oracle response here...
```

## Context Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Audio 1   │────►│ Transcript 1│────►│             │
└─────────────┘     └─────────────┘     │             │
                                        │   Context   │
┌─────────────┐     ┌─────────────┐     │   Builder   │
│   Audio 2   │────►│ Transcript 2│────►│             │
└─────────────┘     └─────────────┘     │             │
                                        └──────┬──────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────┐
│              Complete Context String                 │
│  - All transcripts (chronological)                  │
│  - Previous LLM responses (if enabled)              │
│  - Clear delimiters between entries                 │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│               Oracle Prompt Template                 │
│  "You are a skeptic... {{CONTEXT}} ... respond"     │
└─────────────────────────────────────────────────────┘
                           │
              Context replaces {{CONTEXT}}
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                  Complete Prompt                     │
│  Sent to LLM for response                           │
└─────────────────────────────────────────────────────┘
```

## LLM History Toggle

### What It Does

The "🔗 Histórico: ON/OFF" button controls whether previous oracle responses are included in context.

### When ON (Default)

- All transcripts + all previous LLM responses are included
- Creates "spiral feedback" - oracles can reference each other
- Useful for iterative analysis from multiple perspectives

### When OFF

- Only transcripts are included
- Each oracle response is independent
- Useful for fresh perspectives without prior influence

### Toggle Behavior

1. Click the toggle button in the oracle keyboard
2. Preference is saved to your session
3. Next oracle request uses the new setting
4. Button label updates to show current state

## Chronological Ordering

Context is always built in chronological order:

```
[TRANSCRIÇÃO 1 - 10:30:00]
First transcript...

[ORÁCULO: Cético - 10:32:00]
First oracle feedback...

[TRANSCRIÇÃO 2 - 10:35:00]
Second transcript...

[ORÁCULO: Visionário - 10:37:00]
Second oracle feedback...

[TRANSCRIÇÃO 3 - 10:40:00]
Third transcript...
```

This ensures oracles understand the temporal progression of your session.

## Context Snapshots

Each oracle request captures a "context snapshot" for auditability:

| Field | Description |
|-------|-------------|
| `transcript_count` | Number of transcripts at request time |
| `llm_response_count` | Number of prior LLM responses included |
| `include_llm_history` | Whether LLM history was enabled |
| `total_tokens_estimate` | Rough token estimate for context |

## Best Practices

### 1. Record Multiple Short Audios

Instead of one long recording:
- Record multiple focused voice messages
- Each becomes a separate transcript
- Easier to reference specific sections

### 2. Use LLM History Strategically

**Enable** when:
- Building upon previous analysis
- Comparing different oracle perspectives
- Creating a comprehensive review

**Disable** when:
- Want fresh, unbiased perspective
- Oracle responses are getting repetitive
- Starting a new line of inquiry

### 3. Clear Session for New Topics

If changing topics significantly:
- Finalize current session
- Start new session
- Keeps context focused and relevant

## Handling Large Contexts

### Token Limits

Large sessions may approach LLM token limits. Signs:
- Truncated responses
- Missing details
- LLM errors

### Solutions

1. **Split Sessions**: Keep sessions focused on single topics
2. **Disable History**: Turn off LLM history to reduce context size
3. **New Session**: Start fresh when context grows too large

## Error Handling

### Missing Transcripts

If a transcript file is missing:
- Placeholder `[Transcrição indisponível]` is used
- Warning logged but request continues
- Check session folder for issues

### Missing LLM Responses

If a previous response file is missing:
- Placeholder `[Resposta indisponível]` is used
- Warning logged but request continues
- Context snapshot shows actual counts

## Technical Details

### Context Format

```
[TRANSCRIÇÃO {seq} - {timestamp}]
{transcript content}

[ORÁCULO: {oracle_name} - {timestamp}]
{llm response content}
```

### Timestamp Format

ISO-like format: `YYYY-MM-DD HH:MM:SS`

### File Storage

- Transcripts: `sessions/{id}/transcripts/{seq}_audio.txt`
- LLM responses: `sessions/{id}/llm_responses/{seq}_{oracle}.txt`

## See Also

- [Adding Custom Oracles](tutorial_adding_oracles.md)
- [Session Naming Logic](session_naming_logic.md)
- [Telegram Interaction Guide](telegram_interaction_guide.md)
