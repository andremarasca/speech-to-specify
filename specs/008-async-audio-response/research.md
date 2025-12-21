# Research: Async Audio Response Pipeline

**Feature**: 008-async-audio-response  
**Date**: 2025-12-21  
**Status**: Complete

## Research Tasks

### 1. TTS Provider Selection

**Task**: Avaliar provedores TTS para síntese de fala em português brasileiro.

**Decision**: `edge-tts` (Microsoft Edge TTS)

**Rationale**:
- Gratuito e sem limites de uso (usa API pública do Edge)
- Suporte nativo a pt-BR com vozes neurais de alta qualidade
- Biblioteca Python assíncrona (`edge-tts`) já disponível
- Demonstrado funcional em `.local/edge_tts_generate.py`
- Não requer GPU ou modelo local

**Alternatives Considered**:
| Provider | Pros | Cons | Rejected Because |
|----------|------|------|------------------|
| Google Cloud TTS | Alta qualidade | Custo por caractere, requer setup | Custo + complexidade |
| Azure TTS | Vozes neurais excelentes | Requer assinatura Azure | Custo + dependência cloud |
| OpenAI TTS | Integração com ecossistema | Custo elevado, latência | Custo |
| Coqui TTS | Open source, local | Requer GPU, modelo grande | Recursos de hardware |
| pyttsx3 | Offline, gratuito | Vozes robóticas, baixa qualidade | Qualidade inaceitável |

### 2. Formato de Áudio

**Task**: Definir formato de saída para áudio sintetizado.

**Decision**: OGG Opus

**Rationale**:
- Suportado nativamente pelo Telegram para voice messages
- Excelente compressão com qualidade preservada
- Menor tamanho de arquivo que MP3 para mesma qualidade
- Já demonstrado funcional em `.local/edge_tts_generate.py`

**Alternatives Considered**:
| Format | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| MP3 | Universal | Maior tamanho, não ideal para voice no Telegram | Tamanho + compatibilidade |
| WAV | Sem compressão, máxima qualidade | Arquivos enormes | Tamanho proibitivo |
| WEBM | Boa compressão | Menos suportado | Compatibilidade |

### 3. Integração com Fluxo de Oráculos

**Task**: Identificar ponto de integração ideal no código existente.

**Decision**: Hook após `bot.send_message()` em `_handle_oracle_callback()`

**Rationale**:
- Garante desacoplamento temporal (texto já entregue)
- Método já possui contexto completo (session, oracle, response)
- Usa `asyncio.create_task()` para não bloquear
- Segue padrão existente de operações assíncronas no daemon

**Integration Point** (linha ~1017 em `src/cli/daemon.py`):
```python
await self.bot.send_message(chat_id, msg, reply_markup=keyboard, parse_mode="Markdown")
# ↓ NOVO: Disparar síntese assíncrona aqui
asyncio.create_task(self._synthesize_and_send_audio(...))
```

### 4. Estrutura de Armazenamento

**Task**: Definir onde persistir arquivos de áudio TTS.

**Decision**: `sessions/{session_id}/audio/tts/{sequence}_{oracle_name}.ogg`

**Rationale**:
- Segue padrão existente de `audio/` para arquivos de áudio
- Subdiretório `tts/` isola dos áudios de entrada do usuário
- Naming `{seq}_{oracle}` alinha com `llm_responses/{seq}_{oracle}.txt`
- Facilita garbage collection por sessão

**Directory Structure**:
```
sessions/
└── 2025-12-21_12-02-29/
    ├── metadata.json
    ├── audio/
    │   ├── 001_voice.ogg        # Áudio do usuário (existente)
    │   └── tts/                  # NOVO
    │       ├── 001_cetico.ogg    # TTS da resposta do oráculo
    │       └── 002_pragmatico.ogg
    ├── llm_responses/
    │   ├── 001_cetico.txt
    │   └── 002_pragmatico.txt
    └── transcripts/
```

### 5. Sanitização de Texto

**Task**: Definir estratégia para limpar texto antes de síntese.

**Decision**: Reutilizar funções de `.local/edge_tts_generate.py`

**Rationale**:
- `strip_markdown()` remove formatação markdown incompatível com fala
- `strip_special_characters()` converte símbolos para equivalentes falados
- Já testado e funcional
- Mover para `src/services/tts/text_sanitizer.py`

**Functions to Adapt**:
- `strip_markdown(text: str) -> str`
- `strip_special_characters(text: str) -> str`

### 6. Garbage Collection Strategy

**Task**: Definir política de limpeza de arquivos de áudio.

**Decision**: Limpeza baseada em idade + limite de espaço

**Rationale**:
- Arquivos TTS são derivados e podem ser regenerados
- Sessões ativas preservam seus arquivos
- Política configurável via `TTSConfig`

**Policy**:
```python
class TTSGarbageCollectionPolicy:
    retention_hours: int = 24        # Arquivos > 24h removidos
    max_storage_mb: int = 500        # Limite total de armazenamento
    preserve_active_sessions: bool = True  # Não remove de sessões ativas
```

### 7. Idempotência

**Task**: Garantir que mesma solicitação não gere duplicatas.

**Decision**: Hash do texto + oracle_id + session_id como chave

**Rationale**:
- Se arquivo com mesmo hash existe, retorna existente
- Evita processamento redundante
- Lógica em `TTSService.synthesize()`

**Implementation**:
```python
def _generate_artifact_key(text: str, oracle_id: str, session_id: str) -> str:
    content = f"{session_id}:{oracle_id}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

## Dependencies

### New Dependencies (requirements.txt)

```
edge-tts>=6.1.0  # Microsoft Edge TTS
```

### Existing Dependencies (Already Available)

- `python-telegram-bot` - Para `bot.send_voice()`
- `pydantic-settings` - Para `TTSConfig`
- `asyncio` - Para operações assíncronas

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Edge TTS API indisponível | Áudio não gerado | Graceful degradation - log erro, notifica usuário |
| Texto muito longo | Timeout/falha | Limite configurável, truncar com aviso |
| Disco cheio | Falha de persistência | GC proativo, limite de espaço |
| Concorrência | Duplicatas | Lock por sessão ou hash idempotente |

## Conclusion

Todas as decisões de pesquisa foram tomadas. O sistema utilizará:
- **edge-tts** como provedor TTS
- Formato **OGG Opus** para áudio
- Integração via **asyncio.create_task** após entrega de texto
- Armazenamento em **sessions/{id}/audio/tts/**
- GC baseado em **idade + limite de espaço**
