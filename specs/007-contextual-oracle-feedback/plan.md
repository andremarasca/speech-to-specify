# Implementation Plan: Contextual Oracle Feedback

**Branch**: `007-contextual-oracle-feedback` | **Date**: 2025-12-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-contextual-oracle-feedback/spec.md`

## Summary

Sistema de feedback contextual com oráculos (personalidades LLM) carregados dinamicamente de arquivos markdown. Permite que usuários solicitem feedback de diferentes personalidades através de botões inline no Telegram, com contexto acumulativo que inclui transcrições de áudio e (opcionalmente) respostas anteriores de LLM. A arquitetura plugin-first permite adicionar novos oráculos sem alteração de código.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Telethon (Telegram), httpx (LLM API), pydantic (validation)  
**Storage**: Filesystem (JSON metadata, .txt responses) — consistente com padrão existente em `src/services/session/storage.py`  
**Testing**: pytest, pytest-asyncio  
**Target Platform**: Linux/Windows server  
**Project Type**: Single project  
**Performance Goals**: <200ms para renderização de botões de oráculos (SC-001)  
**Constraints**: callback_data do Telegram limitado a 64 bytes; LLM timeout de 30s  
**Scale/Scope**: Sessões individuais de brainstorm, ~10-50 entradas por sessão

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Como Endereçado |
|-----------|--------|-----------------|
| **I. Latência Zero** | ✅ | Botões renderizados em <200ms (FR); transcrições já disponíveis imediatamente (existente) |
| **II. Excelência Estrutural** | ✅ | OracleManager como plugin loader; novos arquivos .md geram botões automaticamente |
| **III. Integridade de Testes** | ✅ | Testes de contrato para OracleManager, ContextBuilder, e callbacks Telegram |
| **IV. Configuração Externa (CLÁUSULA PÉTREA)** | ✅ | Diretório de oráculos via env var `ORACLES_DIR`; placeholder via `ORACLE_PLACEHOLDER` |
| **V. Persistência de Contexto** | ✅ | Respostas LLM persistidas em `llm_responses/` com metadata no Session model |

**Restrictions Compliance:**
- ✅ Feedback sob demanda (botões, não automático)
- ✅ Interface de botões dinâmicos (não comandos de texto)
- ✅ Agência do usuário preservada (toggle de histórico LLM)

**Tutorial Requirement:**
- ✅ `docs/tutorial_adding_oracles.md` — Como criar e registrar novas personalidades
- ✅ `docs/tutorial_context_management.md` — Gestão da flag include_llm_history

### Post-Design Re-evaluation (Phase 1 Complete)

| Artefato | Validação Constitucional |
|----------|-------------------------|
| **data-model.md** | ✅ LlmEntry e ContextSnapshot permitem auditoria completa (V. Persistência) |
| **oracle-manager.md** | ✅ BC-OM-* garantem extensão via filesystem (II. Excelência) |
| **context-builder.md** | ✅ BC-CB-* cobrem ordenação cronológica e preferências (V. Persistência) |
| **telegram-callbacks.md** | ✅ BC-TC-* mapeiam todos callbacks com testes (III. Integridade) |
| **quickstart.md** | ✅ Configuração via env vars documentada (IV. Configuração Externa) |

**Gate Status**: ✅ PASS — Nenhuma violação identificada. Pronto para Phase 2 (tasks).

## Project Structure

### Documentation (this feature)

```text
specs/007-contextual-oracle-feedback/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── oracle-manager.md
│   ├── context-builder.md
│   └── telegram-callbacks.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── session.py           # EXTEND: Add LlmEntry, include_llm_history
│   └── oracle.py            # NEW: Oracle dataclass
├── services/
│   ├── oracle/              # NEW: Oracle management
│   │   ├── __init__.py
│   │   ├── manager.py       # OracleManager: load, validate, list oracles
│   │   └── loader.py        # Markdown parsing, title extraction
│   ├── llm/
│   │   ├── context_builder.py  # NEW: Build context from session
│   │   ├── prompt_injector.py  # NEW: Inject context into oracle prompt
│   │   └── oracle_client.py    # NEW: LLM API client with timeout handling
│   └── telegram/
│       ├── keyboards.py     # EXTEND: Add build_oracle_keyboard()
│       └── callbacks.py     # EXTEND: Handle oracle selection callbacks
├── cli/
│   └── daemon.py            # EXTEND: Wire oracle callbacks
└── lib/
    └── config.py            # EXTEND: Add OracleConfig

tests/
├── contract/
│   ├── test_oracle_manager_contract.py  # NEW
│   └── test_context_builder_contract.py # NEW
├── integration/
│   └── test_oracle_feedback_flow.py     # NEW
└── unit/
    ├── test_oracle_loader.py            # NEW
    └── test_prompt_injector.py          # NEW

prompts/
└── oracles/                 # NEW: Oracle personality files
    ├── cetico.md
    ├── visionario.md
    └── otimista.md

docs/
├── tutorial_adding_oracles.md           # NEW: Per Constitution Tutorial requirement
└── tutorial_context_management.md       # NEW: Per Constitution Tutorial requirement
```

**Structure Decision**: Single project structure mantido. Nova pasta `src/services/oracle/` para isolar lógica de gerenciamento de oráculos, seguindo padrão existente (`src/services/session/`, `src/services/telegram/`).

## Complexity Tracking

> **No violations identified.** All Constitution principles are addressed without exceptions.
