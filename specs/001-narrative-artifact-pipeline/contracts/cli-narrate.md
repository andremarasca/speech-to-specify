# CLI Contract: narrate

**Command**: `narrate`  
**Purpose**: Transformar texto caótico em artefatos narrativos estruturados

## Synopsis

```
narrate <input-file> [--output-dir <path>] [--provider <name>] [--verbose]
narrate --help
narrate --version
```

## Description

Processa um arquivo de texto desestruturado através de uma cadeia sequencial de transformações LLM, gerando artefatos narrativos progressivamente mais estruturados.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `<input-file>` | Yes | Caminho para arquivo de texto (.txt, .md) contendo o texto caótico a processar |

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `./output` | Diretório base para armazenar execuções |
| `--provider` | `-p` | `openai` | Provedor de LLM: `openai`, `anthropic` |
| `--verbose` | `-v` | `false` | Exibir progresso detalhado durante execução |
| `--help` | `-h` | - | Exibir ajuda e sair |
| `--version` | `-V` | - | Exibir versão e sair |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | If provider=openai | Chave de API da OpenAI |
| `ANTHROPIC_API_KEY` | If provider=anthropic | Chave de API da Anthropic |
| `NARRATE_OUTPUT_DIR` | No | Override para --output-dir (prioridade menor que CLI) |
| `NARRATE_PROVIDER` | No | Override para --provider (prioridade menor que CLI) |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Sucesso - cadeia completa |
| `1` | Erro de uso (argumentos inválidos) |
| `2` | Erro de configuração (env vars ausentes) |
| `3` | Erro de validação (entrada inválida) |
| `4` | Erro de LLM (falha na comunicação com provedor) |
| `5` | Erro interno (falha inesperada) |

## Output Structure

Execução bem-sucedida cria:

```
{output-dir}/
└── executions/
    └── {execution-id}/
        ├── input.md                    # Cópia da entrada original
        ├── execution.json              # Metadados da execução
        ├── artifacts/
        │   ├── 01_constitution.md      # Etapa 1: Contexto normativo
        │   ├── 02_specification.md     # Etapa 2: Valor e escopo
        │   └── 03_planning.md          # Etapa 3: Estrutura de execução
        └── logs/
            └── llm_traffic.jsonl       # Registro de todas interações LLM
```

## Stdout/Stderr Behavior

### Stdout (normal mode)
```
Execution started: {execution-id}
Processing step 1/3: constitution
Processing step 2/3: specification
Processing step 3/3: planning
Execution completed: {output-path}
```

### Stdout (verbose mode)
```
Execution started: {execution-id}
  Input: {input-file} (1234 bytes, hash: abc123...)
  Provider: openai
  Output: {output-dir}
Processing step 1/3: constitution
  Prompt: 1500 chars
  Response: 2300 chars (latency: 1234ms)
  Artifact: {path}
[...]
Execution completed: {output-path}
  Duration: 45.2s
  Artifacts: 3
  LLM calls: 3
```

### Stderr (errors)
```
Error: Input file not found: {path}
Error: Missing required environment variable: OPENAI_API_KEY
Error: Input validation failed: content is empty
Error: LLM request failed: rate limit exceeded
```

## Examples

### Basic usage
```bash
narrate ./notes/brainstorm.txt
```

### With custom output directory
```bash
narrate ./notes/brainstorm.txt --output-dir ./my-artifacts
```

### Using Anthropic provider
```bash
export ANTHROPIC_API_KEY="sk-..."
narrate ./notes/brainstorm.txt --provider anthropic
```

### Verbose execution
```bash
narrate ./notes/brainstorm.txt --verbose
```

## Error Recovery

Em caso de falha parcial:
1. Todos os artefatos gerados até o ponto de falha são preservados
2. Um arquivo `failure.json` é criado em `logs/`
3. O execution.json é atualizado com status `failed`

O usuário pode inspecionar os artefatos parciais e o log de falha para diagnóstico.
