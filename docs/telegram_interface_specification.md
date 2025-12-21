# Especificação da Interface Telegram

> **Propósito**: Documentação completa da interface de comunicação entre o bot Telegram e o usuário final. Serve como base para prototipação desacoplada do sistema.

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Comandos Disponíveis](#comandos-disponíveis)
3. [Tipos de Teclados Inline](#tipos-de-teclados-inline)
4. [Botões e Callbacks](#botões-e-callbacks)
5. [Fluxos de Interação](#fluxos-de-interação)
6. [Mensagens e Templates](#mensagens-e-templates)
7. [Estados da Interface](#estados-da-interface)
8. [Diagramas de Fluxo](#diagramas-de-fluxo)

---

## Visão Geral

O sistema utiliza o Telegram como canal de comunicação com as seguintes características:

- **Comunicação bidirecional**: Comandos de texto, mensagens de voz e cliques em botões
- **Interface inline**: Teclados inline (InlineKeyboardMarkup) anexados às mensagens
- **Dois modos de UI**: Normal (com emojis) e Simplificado (sem emojis)
- **Feedback em tempo real**: Transcrição imediata após cada áudio enviado

### Arquitetura de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                      Usuário Telegram                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   TelegramBotAdapter                         │
│  • Recebe: Commands, Voice, Callbacks                       │
│  • Envia: Messages, Files, Inline Keyboards                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    VoiceOrchestrator                         │
│  • Roteia eventos para handlers específicos                 │
│  • Gerencia estado da conversação                           │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   UIService     │  │ SessionManager  │  │  SearchService  │
│  • Keyboards    │  │  • Lifecycle    │  │  • Name search  │
│  • Messages     │  │  • Storage      │  │  • ID search    │
│  • Progress     │  │  • State        │  │  • Text search  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Comandos Disponíveis

### Comandos de Sessão

| Comando | Descrição | Argumentos | Resposta |
|---------|-----------|------------|----------|
| `/start` | Inicia nova sessão ou mostra boas-vindas | - | Mensagem de boas-vindas ou diálogo de conflito |
| `/done` ou `/finish` | Finaliza sessão ativa | - | Confirmação de finalização |
| `/status [ref]` | Mostra status da sessão | `ref`: ID ou nome (opcional) | Detalhes da sessão com teclado |
| `/reopen [ref]` | Reabre sessão finalizada | `ref`: ID ou nome (opcional) | Lista de sessões ou confirmação |

### Comandos de Gestão

| Comando | Descrição | Argumentos | Resposta |
|---------|-----------|------------|----------|
| `/sessions` | Lista todas as sessões | - | Lista paginada com ações |
| `/list` | Lista arquivos da sessão recente | - | Lista de arquivos com botões |
| `/get <path>` | Baixa arquivo específico | `path`: caminho relativo | Arquivo enviado |
| `/session <ref>` | Busca e ativa sessão | `ref`: ID ou nome | Detalhes da sessão |

### Comandos de Busca

| Comando | Descrição | Argumentos | Resposta |
|---------|-----------|------------|----------|
| `/search <nome>` | Busca sessão por nome | `nome`: termo de busca | Lista de resultados |
| `/searchid <id>` | Busca sessão por ID | `id`: substring do ID | Lista de resultados |
| `/searchtxt <texto>` | Busca em transcrições | `texto`: termo de busca | Lista de resultados |

### Comandos de Conteúdo

| Comando | Descrição | Argumentos | Resposta |
|---------|-----------|------------|----------|
| `/transcripts [ref]` | Ver transcrições completas | `ref`: ID ou nome (opcional) | Texto ou arquivo |
| `/process [id]` | Executa pipeline de processamento | `id`: sessão específica (opcional) | Status do processamento |

### Comandos de Configuração

| Comando | Descrição | Argumentos | Resposta |
|---------|-----------|------------|----------|
| `/preferences` | Configurar interface | `simple`, `normal`, `toggle` | Teclado de preferências |
| `/help` | Ajuda completa | - | Texto de ajuda formatado |

---

## Tipos de Teclados Inline

### KeyboardType Enum

```python
class KeyboardType(str, Enum):
    SESSION_ACTIVE = "SESSION_ACTIVE"
    SESSION_EMPTY = "SESSION_EMPTY"
    PROCESSING = "PROCESSING"
    RESULTS = "RESULTS"
    CONFIRMATION = "CONFIRMATION"
    SESSION_CONFLICT = "SESSION_CONFLICT"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    PAGINATION = "PAGINATION"
    HELP_CONTEXT = "HELP_CONTEXT"
    TIMEOUT = "TIMEOUT"
    SEARCH_RESULTS = "SEARCH_RESULTS"
    SEARCH_NO_RESULTS = "SEARCH_NO_RESULTS"
```

### 1. SESSION_ACTIVE - Sessão Ativa

Exibido quando há uma sessão com áudios sendo coletados.

```
┌───────────────────────────────────────┐
│  [✅ Finalizar]  [📊 Status]         │
├───────────────────────────────────────┤
│           [❓ Ajuda]                  │
└───────────────────────────────────────┘
```

**Versão Simplificada:**
```
┌───────────────────────────────────────┐
│  [Finalizar]  [Status]               │
├───────────────────────────────────────┤
│           [Ajuda]                     │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:finalize` → Finaliza sessão
- `action:status` → Mostra status
- `action:help` → Mostra ajuda contextual

### 2. SESSION_EMPTY - Sessão Vazia

Exibido quando não há sessão ativa.

```
┌───────────────────────────────────────┐
│           [❓ Ajuda]                  │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:help` → Mostra ajuda contextual

### 3. PROCESSING - Processamento em Andamento

Exibido durante operações longas (transcrição, processamento).

```
┌───────────────────────────────────────┐
│       [❌ Cancelar]                   │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:cancel_operation` → Cancela operação

### 4. RESULTS - Resultados Disponíveis

Exibido após transcrição bem-sucedida.

```
┌───────────────────────────────────────┐
│  [📄 Ver Completo]  [🔍 Buscar]      │
├───────────────────────────────────────┤
│  [🚀 Pipeline]  [❓ Ajuda]           │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:view_full` → Mostra transcrição completa
- `action:search` → Inicia fluxo de busca
- `action:pipeline` → Executa pipeline de processamento
- `action:help` → Mostra ajuda contextual

### 5. SESSION_CONFLICT - Conflito de Sessão

Exibido quando `/start` é chamado com sessão ativa.

```
┌───────────────────────────────────────┐
│  [✅ Finalizar Atual]  [🆕 Nova]     │
├───────────────────────────────────────┤
│  [↩️ Voltar à Atual]  [❓ Ajuda]     │
└───────────────────────────────────────┘
```

**Callbacks:**
- `confirm:session_conflict:finalize` → Finaliza sessão atual
- `confirm:session_conflict:new` → Descarta e inicia nova
- `confirm:session_conflict:return` → Retorna à sessão atual
- `action:help` → Mostra ajuda contextual

### 6. ERROR_RECOVERY - Recuperação de Erro

Exibido após falhas recuperáveis.

```
┌───────────────────────────────────────┐
│  [🔄 Tentar Novamente]  [❌ Cancelar]│
├───────────────────────────────────────┤
│           [❓ Ajuda]                  │
└───────────────────────────────────────┘
```

**Callbacks:**
- `retry:last_action` → Repete última ação
- `action:cancel` → Cancela operação
- `action:help` → Mostra ajuda contextual

### 7. PAGINATION - Paginação

Exibido em listagens longas.

```
┌───────────────────────────────────────┐
│  [⬅️ Anterior]  [1/5]  [➡️ Próximo] │
├───────────────────────────────────────┤
│           [✖️ Fechar]                │
└───────────────────────────────────────┘
```

**Callbacks:**
- `page:{n}` → Navega para página n
- `page:current` → (No-op, apenas indicador)
- `action:close` → Fecha listagem

### 8. TIMEOUT - Operação Demorada

Exibido quando operação excede tempo esperado.

```
┌───────────────────────────────────────┐
│  [⏳ Continuar]  [❌ Cancelar]       │
├───────────────────────────────────────┤
│           [❓ Ajuda]                  │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:continue_wait` → Continua aguardando
- `action:cancel_operation` → Cancela operação
- `action:help` → Mostra ajuda contextual

### 9. RECOVERY - Recuperação de Sessão Órfã

Exibido na inicialização quando sessão interrompida é detectada.

```
┌───────────────────────────────────────┐
│  [▶️ Retomar]  [✅ Finalizar]        │
├───────────────────────────────────────┤
│  [🗑️ Descartar]  [❓ Ajuda]          │
└───────────────────────────────────────┘
```

**Callbacks:**
- `recover:resume_session` → Retoma sessão
- `recover:finalize_orphan` → Finaliza e transcreve
- `recover:discard_orphan` → Descarta sessão
- `action:help` → Mostra ajuda contextual

### 10. SEARCH_RESULTS - Resultados de Busca

Exibido após busca com resultados.

```
┌───────────────────────────────────────┐
│  [📁 Sessão 1 (90%)]                 │
├───────────────────────────────────────┤
│  [📁 Sessão 2 (75%)]                 │
├───────────────────────────────────────┤
│  [📁 Sessão 3 (60%)]                 │
├───────────────────────────────────────┤
│  [🔄 Nova Busca]  [✖️ Fechar]        │
└───────────────────────────────────────┘
```

**Callbacks:**
- `search:select:{session_id}` → Seleciona sessão
- `action:search` → Nova busca
- `action:close` → Fecha resultados

### 11. SEARCH_NO_RESULTS - Sem Resultados

Exibido quando busca não retorna resultados.

```
┌───────────────────────────────────────┐
│  [🔄 Nova Busca]  [✖️ Fechar]        │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:search` → Nova busca
- `action:close` → Fecha

### 12. PREFERENCES - Preferências

Exibido pelo comando `/preferences`.

```
┌───────────────────────────────────────┐
│  [Simplificado]  [Normal]            │
├───────────────────────────────────────┤
│           [Alternar]                  │
└───────────────────────────────────────┘
```

**Callbacks:**
- `pref:simple` → Ativa modo simplificado
- `pref:normal` → Ativa modo normal
- `pref:toggle` → Alterna modo

### 13. ORACLE - Feedback de Oráculos

Exibido após transcrição para solicitar feedback de IA.

```
┌───────────────────────────────────────┐
│  [📝 Ver Transcrições]               │
├───────────────────────────────────────┤
│  [🎭 Cético]                         │
├───────────────────────────────────────┤
│  [🎭 Empático]                       │
├───────────────────────────────────────┤
│  [🎭 Otimista]                       │
├───────────────────────────────────────┤
│  [🔗 Histórico: ON]                  │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:view_full` → Ver transcrições
- `oracle:{oracle_id}` → Solicita feedback do oráculo
- `toggle:llm_history` → Alterna histórico de contexto

### 14. SESSIONS_LIST_ACTIONS - Ações de Lista de Sessões

Exibido após listar sessões com `/sessions`.

```
┌───────────────────────────────────────┐
│  [📝 Ver Transcrições]  [📂 Arquivos]│
├───────────────────────────────────────┤
│       [🔓 Reabrir Sessão]            │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:view_full` → Ver transcrições
- `action:list_files` → Listar arquivos
- `action:reopen_menu` → Menu de reabertura

### 15. REOPEN_SESSIONS - Seleção de Sessão para Reabrir

Exibido pelo comando `/reopen` sem argumentos.

```
┌───────────────────────────────────────┐
│  [🔘 Sessão 1 | 3 áudios]           │
├───────────────────────────────────────┤
│  [🔘 Sessão 2 | 5 áudios]           │
├───────────────────────────────────────┤
│  [🔘 Sessão 3 | 2 áudios]           │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:reopen_session:{session_id}` → Reabre sessão específica

### 16. FILE_LIST - Lista de Arquivos

Exibido pelo comando `/list`.

```
┌───────────────────────────────────────┐
│  [🎙️ 001_audio.ogg]                 │
├───────────────────────────────────────┤
│  [📝 001_audio.txt]                  │
├───────────────────────────────────────┤
│  [📄 consolidated.txt]               │
└───────────────────────────────────────┘
```

**Callbacks:**
- `action:get_file:{path}` → Baixa arquivo específico

---

## Botões e Callbacks

### Registro de Callbacks

| Prefixo | Formato | Handler | Descrição |
|---------|---------|---------|-----------|
| `action:` | `action:{name}` | `_handle_action_callback` | Ações diretas |
| `confirm:` | `confirm:{type}:{response}` | `_handle_confirm_callback` | Confirmações |
| `recover:` | `recover:{action}` | `_handle_recover_callback` | Recuperação |
| `page:` | `page:{number}` | `_handle_page_callback` | Paginação |
| `search:` | `search:select:{id}` | `_handle_search_select_callback` | Seleção de busca |
| `pref:` | `pref:{option}` | `_handle_pref_callback` | Preferências |
| `oracle:` | `oracle:{id}` | `_handle_oracle_callback` | Feedback de oráculo |
| `toggle:` | `toggle:{type}` | `_handle_toggle_callback` | Toggles |
| `retry:` | `retry:{action}` | `_handle_retry_callback` | Retentativas |
| `help:` | `help:{topic}` | `_handle_help_callback` | Ajuda contextual |

### Mapeamento de Actions

| Action | Comportamento |
|--------|--------------|
| `finalize` | Finaliza sessão ativa |
| `status` | Mostra status da sessão |
| `help` | Mostra ajuda contextual |
| `cancel` | Cancela sessão sem transcrição |
| `cancel_operation` | Cancela operação em andamento |
| `continue_wait` | Continua aguardando operação |
| `search` | Inicia fluxo de busca |
| `close` | Fecha/descarta mensagem |
| `close_help` | Fecha mensagem de ajuda |
| `view_full` | Mostra transcrição completa |
| `pipeline` | Executa pipeline de processamento |
| `list_sessions` | Lista todas as sessões |
| `list_files` | Lista arquivos da sessão |
| `reopen_menu` | Mostra menu de reabertura |
| `reopen_session:{id}` | Reabre sessão específica |
| `get_file:{path}` | Baixa arquivo específico |
| `dismiss` | Descarta diálogo de confirmação |

---

## Fluxos de Interação

### Fluxo 1: Primeira Utilização

```
Usuário: /start
    │
    ▼
┌─────────────────────────────────────┐
│ 🎙️ Bem-vindo ao Narrate!           │
│                                     │
│ Este bot transcreve suas mensagens  │
│ de voz usando IA local.            │
│                                     │
│ Como usar:                          │
│ 1. 📤 Envie mensagens de voz       │
│ 2. ✅ Toque em "Finalizar"         │
│ 3. 📝 Receba a transcrição         │
└─────────────────────────────────────┘
```

### Fluxo 2: Envio de Áudio

```
Usuário: [Mensagem de Voz]
    │
    ▼
[Typing indicator...]
    │
    ▼
┌─────────────────────────────────────┐
│ 🎙️ Audio #1 (15s)                  │
│ 📂 Session: _minha-sessao_          │
│                                     │
│ 📝 Transcription:                   │
│ ```                                 │
│ Conteúdo transcrito do áudio...    │
│ ```                                 │
│                                     │
│ 💡 Select an oracle for feedback.   │
├─────────────────────────────────────┤
│ [📝 Ver Transcrições]               │
│ [🎭 Cético]                         │
│ [🎭 Empático]                       │
│ [🔗 Histórico: ON]                  │
└─────────────────────────────────────┘
```

### Fluxo 3: Finalização de Sessão

```
Usuário: /done
    │
    ▼
┌─────────────────────────────────────┐
│ ✅ Session Finalized                │
│                                     │
│ 🆔 Session: `2025-12-21_14-30-00`  │
│ 📝 Name: _minha-sessao_             │
│ 🎙️ Audio files: 3                  │
│ ✅ Transcribed: 3/3                 │
│ 📁 Status: TRANSCRIBED              │
│                                     │
│ Use /transcripts to view all.       │
└─────────────────────────────────────┘
```

### Fluxo 4: Conflito de Sessão

```
Usuário: /start (com sessão ativa)
    │
    ▼
┌─────────────────────────────────────┐
│ ⚠️ Sessão em Andamento              │
│                                     │
│ Você já tem uma sessão ativa com    │
│ 3 áudio(s).                         │
│                                     │
│ O que deseja fazer?                 │
├─────────────────────────────────────┤
│ [✅ Finalizar Atual] [🆕 Nova]      │
│ [↩️ Voltar à Atual]  [❓ Ajuda]     │
└─────────────────────────────────────┘
```

### Fluxo 5: Busca de Sessão

```
Usuário: /search reunião
    │
    ▼
┌─────────────────────────────────────┐
│ 🔍 Resultados (nome)                │
│                                     │
│ Encontradas 2 sessão(ões):          │
├─────────────────────────────────────┤
│ [📁 reunião-equipe (90%)]          │
│ [📁 reunião-cliente (75%)]         │
│ [🔄 Nova Busca]  [✖️ Fechar]        │
└─────────────────────────────────────┘
    │
    ▼ (clique em sessão)
    │
┌─────────────────────────────────────┐
│ ✅ Sessão Reaberta                  │
│                                     │
│ 📛 reunião-equipe                   │
│ 🆔 ID: `2025-12-20_10-00-00`       │
│ 🎙️ Áudios existentes: 5            │
│ 📊 Estado: TRANSCRIBED → COLLECTING │
│                                     │
│ Envie mensagens de voz para         │
│ adicionar mais áudio.               │
├─────────────────────────────────────┤
│ [✅ Finalizar]                      │
└─────────────────────────────────────┘
```

### Fluxo 6: Feedback de Oráculo

```
Usuário: [Clica em 🎭 Cético]
    │
    ▼
[Typing indicator...]
    │
    ▼
┌─────────────────────────────────────┐
│ 🎭 Cético                           │
│                                     │
│ [Resposta do LLM com análise        │
│  crítica do conteúdo transcrito]    │
├─────────────────────────────────────┤
│ [📝 Ver Transcrições]               │
│ [🎭 Cético]                         │
│ [🎭 Empático]                       │
│ [🔗 Histórico: ON]                  │
└─────────────────────────────────────┘
```

### Fluxo 7: Recuperação de Sessão Órfã

```
[Daemon reinicia com sessão interrompida]
    │
    ▼
┌─────────────────────────────────────┐
│ ⚠️ Sessão Interrompida Detectada    │
│                                     │
│ Uma sessão anterior não foi         │
│ finalizada corretamente.            │
│                                     │
│ 📁 minha-sessao                     │
│ 🎙️ 3 áudio(s)                      │
│ 📅 Criada em: 2025-12-21 10:00:00  │
│                                     │
│ O que deseja fazer?                 │
├─────────────────────────────────────┤
│ [▶️ Retomar]  [✅ Finalizar]        │
│ [🗑️ Descartar]  [❓ Ajuda]          │
└─────────────────────────────────────┘
```

---

## Mensagens e Templates

### Mensagens de Sessão

| Chave | Mensagem (Normal) | Mensagem (Simplificada) |
|-------|-------------------|-------------------------|
| `SESSION_CREATED` | ✅ Sessão iniciada! Envie mensagens de voz... | Sessão iniciada. Envie mensagens de voz... |
| `AUDIO_RECEIVED` | 🎙️ Áudio {sequence} recebido | Áudio {sequence} recebido |
| `SESSION_FINALIZED` | ✨ Sessão finalizada! {audio_count} áudio(s) processado(s). | Sessão finalizada. {audio_count} áudio(s) processado(s). |
| `NO_ACTIVE_SESSION` | ❌ Nenhuma sessão ativa. Envie uma mensagem de voz para iniciar. | Nenhuma sessão ativa. Envie uma mensagem de voz para iniciar. |

### Mensagens de Progresso

| Chave | Mensagem (Normal) | Mensagem (Simplificada) |
|-------|-------------------|-------------------------|
| `PROGRESS_STARTED` | ⏳ Processando {operation_type}... | Processando {operation_type}... |
| `PROGRESS_UPDATE` | {description} {progress_bar} {percentage}% | {description}: {percentage}% concluído |
| `PROGRESS_COMPLETE` | ✅ Processamento concluído! | Processamento concluído. |

### Mensagens de Busca

| Chave | Mensagem (Normal) | Mensagem (Simplificada) |
|-------|-------------------|-------------------------|
| `SEARCH_PROMPT` | 🔍 Descreva o tema da sessão que procura: | Descreva o tema da sessão que procura: |
| `SEARCH_RESULTS_HEADER` | 📋 Sessões encontradas: | Sessões encontradas: |
| `SEARCH_NO_RESULTS` | ❌ Nenhuma sessão encontrada para sua busca. Tente descrever de outra forma. | Nenhuma sessão encontrada. Tente descrever de outra forma. |
| `SEARCH_TIMEOUT` | ⏰ Busca cancelada por inatividade. | Busca cancelada por inatividade. |

### Mensagens de Oráculo

| Chave | Mensagem (Normal) | Mensagem (Simplificada) |
|-------|-------------------|-------------------------|
| `ORACLE_NO_TRANSCRIPTS` | 📝 Envie um áudio primeiro para receber feedback. | Envie um áudio primeiro para receber feedback. |
| `ORACLE_NOT_FOUND` | ❌ Oráculo não encontrado. A lista foi atualizada. | Oráculo não encontrado. Tente novamente. |
| `ORACLE_TIMEOUT` | ⏱️ Tempo esgotado ao aguardar resposta. Tente novamente. | Tempo esgotado. Tente novamente. |
| `ORACLE_RESPONSE_HEADER` | 🎭 **{oracle_name}** {response} | {oracle_name}: {response} |

### Mensagens de Recuperação

| Chave | Mensagem (Normal) |
|-------|-------------------|
| `RECOVERY_PROMPT` | ⚠️ **Sessão Interrompida Detectada** Uma sessão anterior não foi finalizada corretamente. 📁 {session_name} 🎙️ {audio_count} áudio(s) 📅 Criada em: {created_at} O que deseja fazer? |

---

## Estados da Interface

### Estados de Sessão (SessionState)

```python
class SessionState(str, Enum):
    COLLECTING = "COLLECTING"       # 🟢 Coletando áudios
    FINALIZING = "FINALIZING"       # 🟡 Em finalização
    TRANSCRIBING = "TRANSCRIBING"   # 🟡 Transcrevendo
    TRANSCRIBED = "TRANSCRIBED"     # 🔵 Transcrito
    PROCESSING = "PROCESSING"       # 🟣 Processando pipeline
    PROCESSED = "PROCESSED"         # ✅ Pipeline concluído
    READY = "READY"                 # ⚪ Pronto (estado terminal)
    INTERRUPTED = "INTERRUPTED"     # 🟠 Interrompido (crash)
    ERROR = "ERROR"                 # ❌ Erro
```

### Mapeamento Estado → Teclado

| Estado | Teclado Padrão | Ações Disponíveis |
|--------|----------------|-------------------|
| `COLLECTING` | `SESSION_ACTIVE` | Finalizar, Status, Ajuda |
| `TRANSCRIBING` | `PROCESSING` | Cancelar |
| `TRANSCRIBED` | `RESULTS` + `ORACLE` | Ver, Buscar, Pipeline, Oráculos |
| `PROCESSING` | `PROCESSING` | Cancelar |
| `PROCESSED` | `RESULTS` | Ver arquivos, Pipeline |
| `INTERRUPTED` | `RECOVERY` | Retomar, Finalizar, Descartar |
| `ERROR` | `ERROR_RECOVERY` | Tentar Novamente, Cancelar |

### Preferências de UI (UIPreferences)

```python
@dataclass
class UIPreferences:
    simplified_ui: bool = False        # Sem emojis
    include_llm_history: bool = True   # Incluir histórico no contexto
```

---

## Diagramas de Fluxo

### Ciclo de Vida da Sessão

```
                    ┌─────────────────┐
                    │     START       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   COLLECTING    │◄─────────────────┐
                    │  (sessão ativa) │                  │
                    └────────┬────────┘                  │
                             │                           │
              ┌──────────────┼──────────────┐           │
              │              │              │           │
     [/done]  │              │  [crash]     │  [/reopen]│
              │              │              │           │
              ▼              ▼              │           │
    ┌─────────────┐  ┌─────────────┐       │           │
    │ FINALIZING  │  │ INTERRUPTED │───────┼───────────┘
    └──────┬──────┘  └─────────────┘       │
           │                               │
           ▼                               │
    ┌─────────────┐                        │
    │TRANSCRIBING │                        │
    └──────┬──────┘                        │
           │                               │
    ┌──────┼──────┐                        │
    │      │      │                        │
    ▼      │      ▼                        │
┌───────┐  │  ┌───────┐                    │
│ ERROR │  │  │SUCCESS│                    │
└───────┘  │  └───┬───┘                    │
           │      │                        │
           │      ▼                        │
           │ ┌─────────────┐               │
           │ │ TRANSCRIBED │───────────────┘
           │ └──────┬──────┘
           │        │
           │   [/process]
           │        │
           │        ▼
           │ ┌─────────────┐
           │ │ PROCESSING  │
           │ └──────┬──────┘
           │        │
           │        ▼
           │ ┌─────────────┐
           └►│  PROCESSED  │
             └──────┬──────┘
                    │
                    ▼
             ┌─────────────┐
             │    READY    │
             └─────────────┘
```

### Fluxo de Eventos do Callback

```
┌─────────────────────────────────────────────────────────────┐
│                    Callback Query                            │
│              callback_data: "prefix:value"                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Parse Prefix   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │         │          │          │         │
        ▼         ▼          ▼          ▼         ▼
   ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
   │ action: ││ confirm:││ recover:││ search: ││ oracle: │
   └────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘
        │         │          │          │         │
        ▼         ▼          ▼          ▼         ▼
   ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
   │ Execute ││ Handle  ││ Resume/ ││ Select  ││ Request │
   │  Direct ││ Dialog  ││ Finalize││ Session ││ Feedback│
   │  Action ││ Response││/Discard ││         ││         │
   └─────────┘└─────────┘└─────────┘└─────────┘└─────────┘
```

---

## Apêndice: Labels de Botões

### Modo Normal (com emojis)

```python
BUTTON_FINALIZE = "✅ Finalizar"
BUTTON_STATUS = "📊 Status"
BUTTON_HELP = "❓ Ajuda"
BUTTON_CANCEL = "❌ Cancelar"
BUTTON_RETRY = "🔄 Tentar Novamente"
BUTTON_VIEW_FULL = "📄 Ver Completo"
BUTTON_SEARCH = "🔍 Buscar"
BUTTON_PIPELINE = "🚀 Pipeline"
BUTTON_PREVIOUS = "⬅️ Anterior"
BUTTON_NEXT = "➡️ Próximo"
BUTTON_CLOSE = "✖️ Fechar"
BUTTON_CONTINUE_WAIT = "⏳ Continuar Aguardando"
BUTTON_FINALIZE_CURRENT = "✅ Finalizar Atual"
BUTTON_START_NEW = "🆕 Iniciar Nova"
BUTTON_RETURN_CURRENT = "↩️ Voltar à Atual"
BUTTON_RESUME = "▶️ Retomar"
BUTTON_DISCARD = "🗑️ Descartar"
BUTTON_NEW_SEARCH = "🔄 Nova Busca"
BUTTON_TRY_AGAIN = "🔄 Tentar Novamente"
BUTTON_SESSIONS_LIST = "📋 Ver todas as sessões"
BUTTON_FILES_LIST = "📂 Listar Arquivos"
BUTTON_TRANSCRIPTS = "📝 Ver Transcrições"
BUTTON_REOPEN_MENU = "🔓 Reabrir Sessão"
BUTTON_ORACLE_PREFIX = "🎭"
BUTTON_ORACLE_HISTORY_ON = "🔗 Histórico: ON"
BUTTON_ORACLE_HISTORY_OFF = "🔗 Histórico: OFF"
```

### Modo Simplificado (sem emojis)

```python
BUTTON_FINALIZE_SIMPLIFIED = "Finalizar"
BUTTON_STATUS_SIMPLIFIED = "Status"
BUTTON_HELP_SIMPLIFIED = "Ajuda"
BUTTON_CANCEL_SIMPLIFIED = "Cancelar"
BUTTON_RETRY_SIMPLIFIED = "Tentar Novamente"
BUTTON_VIEW_FULL_SIMPLIFIED = "Ver Completo"
BUTTON_SEARCH_SIMPLIFIED = "Buscar"
BUTTON_PIPELINE_SIMPLIFIED = "Pipeline"
BUTTON_PREVIOUS_SIMPLIFIED = "Anterior"
BUTTON_NEXT_SIMPLIFIED = "Próximo"
BUTTON_CLOSE_SIMPLIFIED = "Fechar"
BUTTON_CONTINUE_WAIT_SIMPLIFIED = "Continuar"
BUTTON_FINALIZE_CURRENT_SIMPLIFIED = "Finalizar Atual"
BUTTON_START_NEW_SIMPLIFIED = "Nova Sessão"
BUTTON_RETURN_CURRENT_SIMPLIFIED = "Voltar"
BUTTON_RESUME_SIMPLIFIED = "Retomar"
BUTTON_DISCARD_SIMPLIFIED = "Descartar"
BUTTON_NEW_SEARCH_SIMPLIFIED = "Nova Busca"
BUTTON_TRY_AGAIN_SIMPLIFIED = "Tentar Novamente"
BUTTON_SESSIONS_LIST_SIMPLIFIED = "Ver todas as sessões"
BUTTON_FILES_LIST_SIMPLIFIED = "Listar Arquivos"
BUTTON_TRANSCRIPTS_SIMPLIFIED = "Ver Transcrições"
BUTTON_REOPEN_MENU_SIMPLIFIED = "Reabrir Sessão"
BUTTON_ORACLE_HISTORY_ON_SIMPLIFIED = "Histórico: ON"
BUTTON_ORACLE_HISTORY_OFF_SIMPLIFIED = "Histórico: OFF"
```

---

## Considerações para Prototipação

### Componentes Reutilizáveis

1. **KeyboardBuilder**: Função que recebe tipo e contexto, retorna estrutura de teclado
2. **MessageFormatter**: Função que recebe template e dados, retorna texto formatado
3. **CallbackRouter**: Mapeamento prefixo → handler
4. **StateManager**: Gerencia transições de estado da UI

### Dados Mock Necessários

```typescript
interface Session {
  id: string;
  intelligible_name: string | null;
  state: SessionState;
  audio_count: number;
  created_at: Date;
}

interface Oracle {
  id: string;
  name: string;
}

interface SearchResult {
  session_id: string;
  session_name: string;
  relevance_score: number;
}

interface UIPreferences {
  simplified_ui: boolean;
  include_llm_history: boolean;
}
```

### Eventos a Simular

1. **Entrada de Usuário**: Comando de texto, mensagem de voz, clique em botão
2. **Respostas do Sistema**: Mensagem com teclado, arquivo, typing indicator
3. **Estados Assíncronos**: Progresso de transcrição, timeout, erro

---

*Documento gerado em: 2025-12-21*
*Versão: 1.0*
