# Quickstart: Async Audio Response Pipeline

**Feature**: 008-async-audio-response  
**Date**: 2025-12-21

## Overview

Este guia permite verificar rapidamente se o pipeline de TTS está funcionando corretamente após implementação.

## Prerequisites

1. **Dependência instalada**:
   ```bash
   pip install edge-tts>=6.1.0
   ```

2. **Variáveis de ambiente** (`.env`):
   ```env
   # TTS Configuration
   TTS_ENABLED=true
   TTS_VOICE=pt-BR-AntonioNeural
   TTS_FORMAT=ogg
   TTS_TIMEOUT_SECONDS=60
   TTS_MAX_TEXT_LENGTH=5000
   TTS_GC_RETENTION_HOURS=24
   TTS_GC_MAX_STORAGE_MB=500
   ```

3. **Bot Telegram configurado** (pré-existente):
   ```env
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_ALLOWED_CHAT_ID=...
   ```

## Quick Verification

### 1. Verificar edge-tts funciona

```bash
# Teste direto da biblioteca
python -c "
import asyncio
import edge_tts

async def test():
    communicate = edge_tts.Communicate('Teste de síntese de fala', 'pt-BR-AntonioNeural')
    await communicate.save('test_output.ogg')
    print('✓ edge-tts funcionando')

asyncio.run(test())
"
```

### 2. Verificar TTSConfig carrega

```bash
python -c "
from src.lib.config import get_tts_config

config = get_tts_config()
print(f'TTS Enabled: {config.enabled}')
print(f'Voice: {config.voice}')
print(f'Format: {config.format}')
print(f'Timeout: {config.timeout_seconds}s')
print('✓ TTSConfig carregado')
"
```

### 3. Verificar TTSService instancia

```bash
python -c "
import asyncio
from pathlib import Path
from src.lib.config import get_tts_config, get_session_config
from src.services.tts import EdgeTTSService

async def test():
    config = get_tts_config()
    sessions_path = get_session_config().sessions_path
    service = EdgeTTSService(config, sessions_path)
    
    healthy = await service.check_health()
    print(f'✓ TTSService health: {healthy}')

asyncio.run(test())
"
```

### 4. Teste End-to-End via Telegram

1. Iniciar o daemon:
   ```bash
   python -m src.cli.daemon
   ```

2. No Telegram:
   - Enviar mensagem de voz para criar sessão
   - Clicar em um botão de oráculo (ex: "🔮 Cético")
   - **Esperado**: 
     - Resposta textual aparece imediatamente
     - Após alguns segundos, áudio é enviado automaticamente

3. Verificar arquivo criado:
   ```bash
   ls sessions/*/audio/tts/
   # Deve mostrar: 001_cetico.ogg (ou similar)
   ```

## Troubleshooting

### Áudio não é enviado

1. Verificar logs:
   ```bash
   # Procurar por erros TTS
   grep -i "tts" logs/*.log
   ```

2. Verificar se TTS está habilitado:
   ```bash
   echo $TTS_ENABLED  # Deve ser "true"
   ```

3. Verificar conectividade (edge-tts usa API Microsoft):
   ```bash
   curl -I https://speech.platform.bing.com
   ```

### Timeout na síntese

1. Aumentar timeout:
   ```env
   TTS_TIMEOUT_SECONDS=120
   ```

2. Verificar tamanho do texto:
   ```bash
   # Se texto > TTS_MAX_TEXT_LENGTH, será rejeitado
   echo $TTS_MAX_TEXT_LENGTH
   ```

### Erro de permissão no diretório

```bash
# Verificar permissões
ls -la sessions/*/audio/

# Criar diretório tts manualmente se necessário
mkdir -p sessions/*/audio/tts/
```

## Expected Behavior

| Ação | Resultado Esperado |
|------|-------------------|
| Oráculo responde | Texto aparece imediatamente |
| Síntese inicia | Log: "TTS synthesis started for..." |
| Síntese completa | Áudio enviado via `send_voice()` |
| Síntese falha | Log de erro, texto permanece disponível |
| Mesmo texto novamente | Usa cache (log: "cached=True") |

## Files Created

Após implementação completa, a estrutura deve incluir:

```
src/
├── models/
│   └── tts.py                    ✓
├── services/
│   └── tts/
│       ├── __init__.py           ✓
│       ├── base.py               ✓
│       ├── edge_tts_service.py   ✓
│       ├── text_sanitizer.py     ✓
│       └── garbage_collector.py  ✓
└── lib/
    └── config.py                 ✓ (TTSConfig added)

tests/
├── unit/
│   ├── test_text_sanitizer.py    ✓
│   └── test_tts_config.py        ✓
├── contract/
│   └── test_tts_service_contract.py ✓
└── integration/
    └── test_tts_integration.py   ✓

docs/
└── tutorial_tts_extensibility.md ✓
```

## Success Criteria Verification

| Critério | Como Verificar |
|----------|---------------|
| SC-001: 95% áudios em <30s | Medir tempo entre texto e áudio no chat |
| SC-002: Zero bloqueio | Texto aparece antes do áudio |
| SC-003: <1% falha silenciosa | Logs mostram erros, não falhas ocultas |
| SC-004: 1 ação para reproduzir | Áudio é enviado automaticamente |
| SC-005: Idempotência | Mesmo oráculo 2x não gera arquivo duplicado |
