# Research – Telegram Contract Fix

## Decisions

### 1) Performance goals for comandos/callbacks
- **Decision:** Estabelecer meta inicial de resposta de UI p95 ≤ 800ms para comandos/callbacks leves (sem transcrição/busca pesada) e p95 ≤ 2s para respostas que consultam storage local de sessões; tarefas assíncronas longas (transcrição, pipeline) continuam fora da rota síncrona e apenas notificam progresso.
- **Rationale:** Mantém UX responsiva em chat, alinhado a bots Telegram típicos e limitações de rede; não depende de infra pesada e é viável on-prem.
- **Alternatives considered:** (a) Não definir meta → risco de regressão silenciosa; (b) metas mais agressivas (≤300ms) → potencialmente irrealista sem profiling/infra dedicada.

### 2) Limites e timeouts operacionais
- **Decision:** Definir via configuração externa: `SEARCH_TIMEOUT=5s`, `PAGINATION_PAGE_SIZE=5`, `HELP_FALLBACK_ENABLED=true`, `ORPHAN_RECOVERY_PROMPT=true`. Tratar timeouts com mensagens de produto e logging estruturado.
- **Rationale:** Valores seguros para MVP com baixo volume; configuráveis evitam hardcoding e permitem ajuste em produção.
- **Alternatives considered:** (a) Valores maiores (10s) → UX mais lenta; (b) inline hardcoding → viola constituição.

### 3) Escala/concorrência
- **Decision:** Suportar operação de instância única do bot com múltiplos chats concorrentes usando asyncio; não há sharding previsto. Registrar como premissa e revisar se carga crescer.
- **Rationale:** Escopo atual é correção contratual; infraestrutura existente opera em instância única. Manter simples reduz risco e effort.
- **Alternatives considered:** (a) Suporte multi-instância/sharding agora → complexidade desnecessária; (b) ignorar concorrência → risco de race em estados de chat.

### 4) Persistência e estado de busca/paginação
- **Decision:** Sessions continuam em filesystem conforme pipeline atual; estado de paginação permanece TODO controlado (roteamento seguro) até implementação futura. Para MVP, armazenar estado de "aguardando query" por chat em memória (dict) no orchestrator, com limpeza após conclusão/timeout.
- **Rationale:** Segue fluxo existente; evita redesign de storage; mantém contrato seguro mesmo sem paginação implementada.
- **Alternatives considered:** (a) Persistir paginação completa em disco/DB agora → esforço maior; (b) não rastrear estado → callbacks inválidos.

### 5) Observabilidade mínima
- **Decision:** Logging estruturado (níveis warning para parâmetros inválidos, error para falhas de backend) com campos `chat_id`, `session_id`, `callback_prefix`, `command`.
- **Rationale:** Atende constituição (detectabilidade) e facilita troubleshooting sem expor stacktrace ao usuário.
- **Alternatives considered:** (a) Apenas prints ou logs genéricos → difícil correlação; (b) telemetria complexa agora → escopo extra.
