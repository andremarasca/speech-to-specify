# Implementation Plan: Async Audio Response Pipeline

**Branch**: `008-async-audio-response` | **Date**: 2025-12-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-async-audio-response/spec.md`

## Summary

Implementar serviço de síntese de fala (TTS) desacoplado e assíncrono que gera áudio das respostas dos oráculos após entrega textual imediata ao usuário. A síntese ocorre em background via `edge-tts`, persistindo artefatos em estrutura de sessão com garbage collection configurável. O usuário recebe texto instantaneamente e áudio quando disponível, sem bloqueio.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: edge-tts (TTS), python-telegram-bot (notificação), pydantic-settings (config)  
**Storage**: Sistema de arquivos local - `sessions/{session_id}/audio/tts/`  
**Testing**: pytest + pytest-asyncio  
**Target Platform**: Linux server / Windows dev  
**Project Type**: Single project (extensão do sistema existente)  
**Performance Goals**: Áudio disponível em <30s após entrega de texto (SC-001)  
**Constraints**: Síntese NUNCA bloqueia resposta textual; timeout configurável (default 60s)  
**Scale/Scope**: Single user (Telegram 1:1), ~50 respostas/dia típico

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio Constitucional | Status | Implementação |
|--------------------------|--------|---------------|
| **Desacoplamento assíncrono** | ✅ | `asyncio.create_task()` após `bot.send_message()` em `_handle_oracle_callback` |
| **Estrutura SOLID com contratos** | ✅ | Interface `TTSService` em `src/services/tts/base.py`, implementação `EdgeTTSService` |
| **Regra binária de testes** | ✅ | Testes obrigatórios para sanitização, contrato, integração |
| **Configuração externa** | ✅ | `TTSConfig` com TTS_VOICE, TTS_FORMAT, TTS_TIMEOUT, TTS_ENABLED via env |
| **Ciclo de vida de áudio** | ✅ | GC via `TTSGarbageCollector` com política de retenção configurável |
| **Tutorial de extensibilidade** | ✅ | `docs/tutorial_tts_extensibility.md` obrigatório |

## Project Structure

### Documentation (this feature)

```text
specs/008-async-audio-response/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── tts-service.md   # TTSService interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/
│   └── tts.py                    # TTSRequest, TTSResult, TTSArtifact
├── services/
│   └── tts/
│       ├── __init__.py
│       ├── base.py               # TTSService interface
│       ├── edge_tts_service.py   # EdgeTTS implementation
│       ├── text_sanitizer.py     # strip_markdown, strip_special_characters
│       └── garbage_collector.py  # TTSGarbageCollector
├── cli/
│   └── daemon.py                 # Integration point: _handle_oracle_callback
└── lib/
    └── config.py                 # TTSConfig extension

tests/
├── unit/
│   ├── test_text_sanitizer.py
│   └── test_tts_config.py
├── contract/
│   └── test_tts_service_contract.py
└── integration/
    └── test_tts_integration.py

docs/
└── tutorial_tts_extensibility.md
```

**Structure Decision**: Single project structure (existing pattern). O serviço TTS é adicionado como novo módulo em `src/services/tts/` seguindo a estrutura existente de `src/services/oracle/`.

## Reference Implementation

**Exemplo TTS Existente**: `.local/edge_tts_generate.py`
- Demonstra uso de `edge-tts` com sanitização de markdown
- Voz configurável: `pt-BR-AntonioNeural`
- Formato de saída: `ogg`
- Funções reutilizáveis: `strip_markdown()`, `strip_special_characters()`

**Ponto de Integração**: `src/cli/daemon.py` → `_handle_oracle_callback()`
```python
# Após linha ~1017:
await self.bot.send_message(chat_id, msg, reply_markup=keyboard, parse_mode="Markdown")
# NOVO: Disparar síntese assíncrona
asyncio.create_task(self._synthesize_and_send_audio(chat_id, response.content, active, oracle))
```

## Complexity Tracking

> Nenhuma violação constitucional identificada. Todas as decisões seguem princípios estabelecidos.
