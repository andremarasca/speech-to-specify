# Data Model: Constituidor de Artefatos Narrativos

**Feature**: 001-narrative-artifact-pipeline  
**Date**: 2025-12-18  
**Source**: [spec.md](spec.md) Key Entities section

## Entity Definitions

### Input (Entrada)

Texto desestruturado fornecido pelo usuário como ponto de partida para a cadeia de transformação.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Identificador único da entrada |
| `content` | str | Yes | Conteúdo bruto do texto (não vazio) |
| `content_hash` | str | Yes | SHA-256 do conteúdo para verificação de integridade |
| `source_path` | str | No | Caminho do arquivo original (se aplicável) |
| `created_at` | datetime | Yes | Timestamp ISO 8601 UTC de recebimento |

**Validation Rules**:
- `content` não pode ser vazio ou apenas whitespace
- `content_hash` deve corresponder ao hash calculado do `content`
- `created_at` deve ser timezone-aware (UTC)

**State Transitions**: Nenhuma. Input é imutável após criação.

---

### Artifact (Artefato)

Documento gerado por uma etapa de transformação na cadeia narrativa.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Identificador único do artefato |
| `execution_id` | UUID | Yes | Referência à execução que gerou este artefato |
| `step_number` | int | Yes | Número da etapa na cadeia (1-indexed) |
| `step_name` | str | Yes | Nome semântico da etapa (e.g., "constitution", "specification") |
| `predecessor_id` | UUID | No | ID do artefato predecessor (null para step 1) |
| `content` | str | Yes | Conteúdo estruturado gerado |
| `created_at` | datetime | Yes | Timestamp ISO 8601 UTC de criação |

**Validation Rules**:
- `step_number` >= 1
- `predecessor_id` é obrigatório se `step_number` > 1
- `predecessor_id` deve referenciar artefato existente na mesma execução
- `step_name` deve pertencer ao conjunto de etapas definidas

**State Transitions**: Nenhuma. Artifact é imutável após criação.

**Relationships**:
- Pertence a uma Execution (many-to-one)
- Referencia predecessor Artifact (self-referential, optional)

---

### Execution (Execução)

Instância de processamento de uma entrada através da cadeia completa.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Identificador único da execução |
| `input_id` | UUID | Yes | Referência à entrada processada |
| `status` | enum | Yes | Estado atual: `in_progress`, `completed`, `failed` |
| `started_at` | datetime | Yes | Timestamp de início |
| `completed_at` | datetime | No | Timestamp de conclusão (se completed/failed) |
| `current_step` | int | No | Etapa atual em processamento (se in_progress) |
| `total_steps` | int | Yes | Total de etapas na cadeia |
| `error_message` | str | No | Mensagem de erro (se failed) |

**Validation Rules**:
- `status` válido: `in_progress`, `completed`, `failed`
- `completed_at` obrigatório se `status` != `in_progress`
- `error_message` obrigatório se `status` == `failed`
- `current_step` <= `total_steps`

**State Transitions**:
```
in_progress → completed (all steps successful)
in_progress → failed (any step fails)
```

**Relationships**:
- Referencia Input (many-to-one)
- Contém Artifacts (one-to-many)
- Contém LLMLogs (one-to-many)
- Pode conter FailureLog (one-to-one, optional)

---

### LLMLog (Registro de LLM)

Registro de uma interação com provedor de LLM.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Identificador único do registro |
| `execution_id` | UUID | Yes | Referência à execução |
| `step_number` | int | Yes | Etapa que gerou esta interação |
| `provider` | str | Yes | Nome do provedor (e.g., "openai", "anthropic") |
| `prompt` | str | Yes | Prompt enviado ao LLM |
| `response` | str | Yes | Resposta recebida do LLM |
| `prompt_sent_at` | datetime | Yes | Timestamp de envio do prompt |
| `response_received_at` | datetime | Yes | Timestamp de recebimento da resposta |
| `latency_ms` | int | Yes | Latência em milissegundos |

**Validation Rules**:
- `prompt` não pode ser vazio
- `response` não pode ser vazio (validação pós-recebimento)
- `response_received_at` >= `prompt_sent_at`
- `latency_ms` >= 0

**State Transitions**: Nenhuma. LLMLog é imutável após criação.

**Relationships**:
- Pertence a uma Execution (many-to-one)

---

### FailureLog (Registro de Falha)

Registro de falha durante processamento.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Identificador único do registro |
| `execution_id` | UUID | Yes | Referência à execução que falhou |
| `failed_step` | int | Yes | Etapa onde ocorreu a falha |
| `error_type` | str | Yes | Tipo de erro (e.g., "LLMError", "ValidationError") |
| `error_message` | str | Yes | Mensagem descritiva do erro |
| `stack_trace` | str | No | Stack trace para debug (opcional) |
| `system_state` | dict | No | Estado do sistema no momento da falha |
| `occurred_at` | datetime | Yes | Timestamp da falha |

**Validation Rules**:
- `error_type` deve ser classe de exceção conhecida
- `failed_step` >= 1

**State Transitions**: Nenhuma. FailureLog é imutável após criação.

**Relationships**:
- Pertence a uma Execution (one-to-one)

---

## Entity Relationship Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─────────┐       ┌─────────────┐       ┌─────────────┐        │
│  │  Input  │──────<│  Execution  │>──────│  Artifact   │        │
│  └─────────┘  1:N  └─────────────┘  1:N  └─────────────┘        │
│                           │                     │                │
│                           │                     │ predecessor    │
│                           │                     └────────┘       │
│                           │                                      │
│                     ┌─────┴─────┐                                │
│                     │           │                                │
│                ┌────┴───┐  ┌────┴─────┐                          │
│                │ LLMLog │  │FailureLog│                          │
│                │  (N)   │  │  (0..1)  │                          │
│                └────────┘  └──────────┘                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Persistence Format

### Input Storage
- Format: Markdown (.md)
- Location: `output/executions/{execution_id}/input.md`

### Artifact Storage
- Format: Markdown (.md)
- Location: `output/executions/{execution_id}/artifacts/{step_number:02d}_{step_name}.md`

### Execution Metadata
- Format: JSON (.json)
- Location: `output/executions/{execution_id}/execution.json`

### LLM Logs
- Format: JSONL (one JSON object per line)
- Location: `output/executions/{execution_id}/logs/llm_traffic.jsonl`

### Failure Logs
- Format: JSON (.json)
- Location: `output/executions/{execution_id}/logs/failure.json`

## Invariants

1. **Immutability**: Todas as entidades são imutáveis após persistência
2. **Referential Integrity**: Toda referência (execution_id, predecessor_id, input_id) deve apontar para entidade existente
3. **Temporal Ordering**: Timestamps devem respeitar ordem causal (created_at < completed_at, prompt_sent_at < response_received_at)
4. **Chain Integrity**: Artefatos formam cadeia linear sem gaps (step 1, 2, 3... N)
5. **Failure Preservation**: Em caso de falha, todos os artefatos até step N-1 devem existir e estar íntegros
