# Implementation Plan: Constituidor de Artefatos Narrativos

**Branch**: `001-narrative-artifact-pipeline` | **Date**: 2025-12-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-narrative-artifact-pipeline/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Sistema para transformar texto caótico em artefatos textuais estruturados por meio de uma cadeia determinística de prompts e LLMs. O sistema opera com arquitetura linear orientada a fluxo, separando três responsabilidades: orquestração do fluxo narrativo, abstração de acesso a LLMs (provedores intercambiáveis), e persistência observável (rastreabilidade total). Extensibilidade por adição, não modificação.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: httpx (HTTP client), pydantic (validação), python-dotenv (env vars)  
**Storage**: Sistema de arquivos local (JSON/Markdown para artefatos, JSONL para logs)  
**Testing**: pytest + pytest-cov  
**Target Platform**: CLI multiplataforma (Windows, Linux, macOS)  
**Project Type**: single - projeto CLI monolítico  
**Performance Goals**: Processamento de documentos até 100KB em tempo razoável (< 5min dependente de LLM)  
**Constraints**: Sem UI gráfica, sem transcrição de áudio, chaves apenas via env vars  
**Scale/Scope**: Uso individual/equipe pequena, ~10 execuções/dia típico

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Check (Phase 0) ✅

Confirm this plan explicitly addresses:

- ✅ **Determinism and replayability**: Cadeia de transformação fixa e sequencial; mesma entrada → mesma sequência de artefatos; configuração explícita via env vars e arquivos; sem estado oculto ou decisões em runtime
- ✅ **Auditability**: Todo prompt/resposta registrado com timestamp em JSONL; artefatos persistidos antes da próxima etapa; falhas registradas como eventos auditáveis; histórico completo reconstruível
- ✅ **Clear boundaries**: Três responsabilidades separadas (orquestração, LLM abstraction, persistência); contratos explícitos via Protocol/ABC; etapas com input/output definidos
- ✅ **Human-in-the-loop safety**: Nenhuma ação irreversível sem entrada explícita; sistema apenas organiza e registra; não corrige/interpreta; falhas preservam trabalho parcial
- ✅ **Validation and test coverage**: pytest com testes unitários (lógica pura), de contrato (interfaces), e integração (fixtures); TDD obrigatório por constituição
- ✅ **Data minimization/privacy defaults**: Chaves apenas em env vars; sem persistência de segredos; logs contêm apenas prompts/respostas (opt-in pelo usuário ao usar o sistema)

### Post-Design Check (Phase 1) ✅

Re-verification after design artifacts generated:

| Principle | Design Artifact | Verification |
|-----------|-----------------|--------------|
| **Determinism** | [data-model.md](data-model.md) - Entidades imutáveis, timestamps UTC, UUIDs | ✅ Fluxo sequencial explícito, sem branching |
| **Auditability** | [contracts/persistence.md](contracts/persistence.md) - JSONL append-only, execution.json | ✅ Toda interação rastreável por ID |
| **Clear boundaries** | [contracts/llm-provider.md](contracts/llm-provider.md) - Protocol, error hierarchy | ✅ Contratos tipados, responsabilidades isoladas |
| **Human-in-the-loop** | [contracts/cli-narrate.md](contracts/cli-narrate.md) - Exit codes, error messages | ✅ Falhas explícitas, sem magic |
| **Test coverage** | [research.md](research.md) - Fixture strategy, mock provider | ✅ Contract tests definidos |
| **Data minimization** | [quickstart.md](quickstart.md) - Env vars only | ✅ Sem storage de secrets |

**Post-Design Status**: All constitution requirements validated against design artifacts.

## Project Structure

### Documentation (this feature)

```text
specs/001-narrative-artifact-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contracts, LLM adapter contract)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/              # Domain entities: Input, Artifact, Execution, LLMLog, FailureLog
│   ├── __init__.py
│   ├── input.py
│   ├── artifact.py
│   ├── execution.py
│   └── logs.py
├── services/            # Business logic: orchestration, LLM abstraction, persistence
│   ├── __init__.py
│   ├── orchestrator.py  # Fluxo narrativo: sequência de etapas
│   ├── llm/             # LLM provider abstraction
│   │   ├── __init__.py
│   │   ├── base.py      # Protocol/ABC para provedores
│   │   ├── openai.py    # Adaptador OpenAI
│   │   └── anthropic.py # Adaptador Anthropic
│   └── persistence/     # Storage abstraction
│       ├── __init__.py
│       ├── artifacts.py # Persistência de artefatos
│       └── logs.py      # Persistência de logs LLM
├── cli/                 # Command-line interface
│   ├── __init__.py
│   └── main.py          # Entry point: narrate command
└── lib/                 # Shared utilities
    ├── __init__.py
    ├── config.py        # Configuração via env vars
    └── timestamps.py    # Timestamp utilities

tests/
├── conftest.py          # Fixtures compartilhadas
├── contract/            # Testes de contrato (interfaces)
│   ├── test_llm_provider.py
│   └── test_persistence.py
├── integration/         # Testes de integração (com fixtures)
│   └── test_orchestrator.py
└── unit/                # Testes unitários (lógica pura)
    ├── test_models.py
    └── test_config.py

prompts/                 # Prompt templates (contratos narrativos)
├── constitution.md      # Template: contexto normativo
├── specification.md     # Template: valor e escopo
└── planning.md          # Template: estruturação de execução
```

**Structure Decision**: Single project CLI (Option 1) selecionado. Estrutura reflete separação de três responsabilidades (models/services/cli) com subdiretórios para LLM abstraction e persistence. Prompts vivem fora de src/ como artefatos de domínio versionáveis.

## Complexity Tracking

> Nenhuma violação identificada. Arquitetura segue princípios constitucionais.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |
