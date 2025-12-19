# Implementation Plan: Telegram Contract Fix

**Branch**: `001-telegram-contract-fix` | **Date**: 2025-12-19 | **Spec**: [specs/001-telegram-contract-fix/spec.md](specs/001-telegram-contract-fix/spec.md)
**Input**: Feature specification from `/specs/001-telegram-contract-fix/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Corrigir a quebra de contrato entre o TelegramBotAdapter e o VoiceOrchestrator: todos os comandos e callbacks expostos devem ter handlers mapeados, respostas em linguagem de produto e testes automatizados. Busca semântica unifica `/search <query>` e fluxo conversacional via `_process_search_query`; recuperação de sessões órfãs, ajuda contextual/fallback e preferências de UI devem ser consistentes e observáveis. Paginação mantém roteamento seguro (`page:`) com TODO explícito para estado de página.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.x (asyncio)  
**Primary Dependencies**: python-telegram-bot, pytest; domain services (session_manager, ui_service)  
**Storage**: Filesystem sessions/transcripts (existing sessions dir); external pipeline/config (NEEDS CLARIFICATION for persistence specifics)  
**Testing**: pytest (unit/integration outlined)  
**Target Platform**: Linux/Windows host running Telegram bot daemon  
**Project Type**: single  
**Performance Goals**: NEEDS CLARIFICATION (latência p95 para comandos/callbacks, throughput de busca)  
**Constraints**: NEEDS CLARIFICATION (limites de paginação, timeouts de busca/transcrição, memória)  
**Scale/Scope**: Single bot instance; usuários simultâneos não especificados (NEEDS CLARIFICATION)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Confirm this plan explicitamente aborda:

- Contrato Telegram completo (todos os comandos/callbacks mapeados, versionados conceitualmente e cobertos por testes automatizados)
- Estrutura SOLID/Object Calisthenics (extensão via composição, acoplamento mínimo entre Telegram, orquestrador e domínio)
- Zero tolerância a falhas (pipeline falha se qualquer teste relevante da interface falhar; refatorações não quebram comportamento observável)
- Observabilidade e recuperação (logs acionáveis, detecção de sessões órfãs e caminhos claros de retomada/finalização)
- Configuração externa (nenhum hardcoding de valores operacionais; novos parâmetros surgem em env/config auditáveis)
- Testabilidade nativa (cada teclado/callback/comando validado por testes automatizados, sem dependência de testes manuais)

Gate status: ✅ Planned compliance via explicit command/callback maps, fallback messaging, and mandated pytest coverage; ✅ observability with structured warnings for invalid callbacks/busca falha; ✅ external config for tokens/limits; ⚠ performance goals/limits NEED CLARIFICATION (to be resolved in research).

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: Single-project layout; use existing `src/` (cli, services, models, lib) and `tests/` (unit, integration, contract). Feature changes localized to `src/cli/daemon.py`, `src/services/telegram/`, `src/lib/` helpers if needed, and keyboards/UI in `src/services/telegram/ui_service.py` / `src/services/telegram/keyboards.py`. Tests under `tests/unit/` and `tests/integration/` per listed files.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
