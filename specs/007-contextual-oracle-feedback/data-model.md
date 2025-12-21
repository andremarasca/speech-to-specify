# Data Model: Contextual Oracle Feedback

**Feature**: 007-contextual-oracle-feedback  
**Date**: 2025-12-20

## Entity Relationship Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                          Session                                 │
│  - id: str                                                       │
│  - state: SessionState                                           │
│  - audio_entries: list[AudioEntry]                              │
│  - llm_entries: list[LlmEntry]        ◄── NEW                   │
│  - ui_preferences: UIPreferences                                 │
│       └── include_llm_history: bool   ◄── NEW                   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
┌─────────────────────┐     ┌─────────────────────┐
│     AudioEntry      │     │      LlmEntry       │  ◄── NEW
│  - sequence: int    │     │  - sequence: int    │
│  - received_at      │     │  - created_at       │
│  - transcript_...   │     │  - oracle_name      │
└─────────────────────┘     │  - oracle_id        │
                            │  - response_filename│
                            │  - context_snapshot │
                            └─────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          Oracle                                  │  ◄── NEW
│  - id: str (8-char hash)                                        │
│  - name: str (extracted from markdown title)                    │
│  - file_path: Path                                              │
│  - prompt_content: str                                          │
│  - placeholder: str (default: {{CONTEXT}})                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       ContextSnapshot                            │  ◄── NEW
│  - transcript_count: int                                        │
│  - llm_response_count: int                                      │
│  - include_llm_history: bool                                    │
│  - total_tokens_estimate: int (optional)                        │
└─────────────────────────────────────────────────────────────────┘
```

## New Entities

### Oracle

Represents a loaded oracle personality from the filesystem.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | str | 8-character SHA256 hash of file path | Unique, immutable |
| `name` | str | Display name extracted from markdown H1 | Non-empty, stripped |
| `file_path` | Path | Absolute path to the .md file | Exists, readable |
| `prompt_content` | str | Full content of the markdown file | Non-empty |
| `placeholder` | str | Placeholder string for context injection | Default: `{{CONTEXT}}` |

**Validation Rules**:
- File must exist and be readable
- First line must contain H1 heading (`# Title`) or fallback to filename
- If placeholder not found in content, use append mode

**State Transitions**: N/A (stateless, reloaded from filesystem)

### LlmEntry

Represents one LLM response stored in a session.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `sequence` | int | 1-indexed order of LLM responses in session | >= 1 |
| `created_at` | datetime | Timestamp when response was generated | UTC |
| `oracle_name` | str | Display name of the oracle used | Non-empty |
| `oracle_id` | str | 8-char hash identifier of the oracle | Matches Oracle.id |
| `response_filename` | str | Filename in llm_responses/ folder | Pattern: `{seq}_{name}.txt` |
| `context_snapshot` | ContextSnapshot | State of context at request time | Embedded object |

**Validation Rules**:
- `sequence` must be unique within session's llm_entries
- `response_filename` must exist in session's llm_responses/ directory
- `oracle_id` should match a known oracle (warning if orphaned)

### ContextSnapshot

Captures the context state at the moment of an LLM request (for auditability).

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `transcript_count` | int | Number of transcripts included | >= 0 |
| `llm_response_count` | int | Number of prior LLM responses included | >= 0 |
| `include_llm_history` | bool | Whether LLM history was enabled | - |
| `total_tokens_estimate` | int | Estimated token count (optional) | >= 0 or None |

## Extended Entities

### UIPreferences (extend existing)

Add field to existing UIPreferences in `src/models/ui_state.py`:

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `include_llm_history` | bool | Include prior LLM responses in context | `True` |

### Session (extend existing)

Add field to existing Session in `src/models/session.py`:

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `llm_entries` | list[LlmEntry] | Ordered list of LLM responses | `[]` |

## Filesystem Structure

```text
sessions/{session_id}/
├── metadata.json           # Session JSON (includes llm_entries)
├── audio/
│   └── {seq}_audio.ogg
├── transcripts/
│   └── {seq}_audio.txt
└── llm_responses/          # NEW directory
    └── {seq}_{oracle_name}.txt

prompts/
└── oracles/                # NEW directory (configurable via ORACLES_DIR)
    ├── cetico.md
    ├── visionario.md
    └── otimista.md
```

## JSON Schema Examples

### metadata.json (Session with LLM entries)

```json
{
  "session_id": "2025-12-20_10-30-00",
  "state": "COLLECTING",
  "audio_entries": [...],
  "llm_entries": [
    {
      "sequence": 1,
      "created_at": "2025-12-20T10:32:15Z",
      "oracle_name": "Cético",
      "oracle_id": "a1b2c3d4",
      "response_filename": "001_cetico.txt",
      "context_snapshot": {
        "transcript_count": 3,
        "llm_response_count": 0,
        "include_llm_history": true,
        "total_tokens_estimate": 1250
      }
    },
    {
      "sequence": 2,
      "created_at": "2025-12-20T10:40:30Z",
      "oracle_name": "Visionário",
      "oracle_id": "e5f6g7h8",
      "response_filename": "002_visionario.txt",
      "context_snapshot": {
        "transcript_count": 3,
        "llm_response_count": 1,
        "include_llm_history": true,
        "total_tokens_estimate": 1850
      }
    }
  ],
  "ui_preferences": {
    "simplified_buttons": false,
    "include_llm_history": true
  }
}
```

### Oracle file (cetico.md)

```markdown
# Cético

Você é um pensador cético e rigoroso. Seu papel é desafiar as ideias apresentadas, identificar falhas lógicas, questionar premissas não fundamentadas e exigir evidências.

## Contexto do Usuário

{{CONTEXT}}

## Instruções

Analise o contexto acima e forneça um feedback crítico e construtivo. Identifique:
1. Premissas questionáveis
2. Lacunas no raciocínio
3. Possíveis contra-argumentos
4. Sugestões de refinamento

Seja direto mas respeitoso. Seu objetivo é fortalecer o pensamento, não desencorajá-lo.
```

## Configuration

### New Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ORACLES_DIR` | Path | `prompts/oracles` | Directory containing oracle .md files |
| `ORACLE_PLACEHOLDER` | str | `{{CONTEXT}}` | Default placeholder for context injection |
| `ORACLE_CACHE_TTL` | int | `10` | Seconds to cache oracle list |
| `LLM_TIMEOUT_SECONDS` | int | `30` | Timeout for LLM requests |
