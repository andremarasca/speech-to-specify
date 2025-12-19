# Feature Specification: Telegram Contract Fix

**Feature Branch**: `001-telegram-contract-fix`  
**Created**: 2025-12-19  
**Status**: Draft  
**Input**: User description: "O problema central é a quebra de contrato entre a interface Telegram do Narrate Bot e o backend de orquestração de sessões de voz‑para‑texto..."

**Constitution**: This spec MUST be compatible with `.specify/memory/constitution.md`.

**Constitution Gates (Telegram Interface)**:
- Mapear e versionar conceitualmente todos os comandos/callbacks, sem handlers ausentes
- Projetar estrutura em linha com SOLID/Object Calisthenics, evitando if/else ad hoc
- Garantir testes automatizados cobrindo contratos de interface; qualquer falha bloqueia entrega
- Planejar observabilidade e caminhos de recuperação (anomalies, sessões órfãs, retomada/finalização)
- Definir toda configuração como externa (env/config); hardcoding é proibido
- Assegurar testabilidade independente de cada fluxo/teclado, sem depender de testes manuais

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sessão gravar/finalizar confiável (Priority: P1)

Usuário inicia e encerra uma sessão de gravação via comandos `/start`, `/done` ou `/finish`, consulta `/status`, recebe teclados inline consistentes e nunca encontra “Unknown command” ou botões inertes.

**Why this priority**: É o fluxo base de captura; qualquer quebra inviabiliza o produto e bloqueia evolução.

**Independent Test**: Executar `/start` → enviar 2 áudios mock → `/status` → `/done` e verificar mensagens, teclados e transição para transcrição sem erros.

**Acceptance Scenarios**:

1. **Given** uma conversa sem sessão ativa, **When** o usuário envia `/start`, **Then** o bot cria sessão, confirma criação e apresenta opções de finalizar, status e ajuda.
2. **Given** sessão ativa, **When** o usuário envia `/done` ou `/finish`, **Then** o bot finaliza, inicia transcrição, comunica progresso e disponibiliza acesso às transcrições.
3. **Given** sessão ativa, **When** o usuário toca em um botão de ajuda contextual, **Then** o bot responde com ajuda específica do estado atual sem erros nem callbacks órfãos.

---

### User Story 2 - Busca e navegação de sessões (Priority: P1)

Usuário encontra e abre sessões antigas por conteúdo usando comando `/search <query>` ou fluxo conversacional com botão “Buscar”, navega resultados com callbacks `search:*`/`page:*`, seleciona um item e recebe resumo com novas ações.

**Why this priority**: Busca semântica é a principal adição da branch 006; precisa ser íntegra para entregar valor prometido.

**Independent Test**: Criar sessões indexadas de teste → acionar `/search query` → receber lista paginada → usar callbacks `search:select:<id>` e `page:<n>` → abrir sessão e verificar ações disponíveis.

**Acceptance Scenarios**:

1. **Given** há sessões indexadas, **When** o usuário envia `/search planejamento financeiro`, **Then** o bot retorna resultados relevantes com botões de seleção e paginação, sem erros técnicos.
2. **Given** resultados exibidos, **When** o usuário clica `search:select:<id>`, **Then** o bot carrega a sessão, mostra resumo e oferece ações (transcrições, processar, reabrir).
3. **Given** paginação disponível, **When** o usuário clica `page:<n>`, **Then** o bot navega para a página solicitada ou reconhece input inválido com aviso amigável mantendo o estado consistente.

---

### User Story 3 - Recuperação, ajuda e preferências (Priority: P2)

Usuário retoma sessões órfãs após reinício do daemon, recebe ajuda contextual ou fallback completo e ajusta preferências via `/preferences` para modo simplificado, com todos os callbacks de recuperação/ajuda executando ou reconhecendo o clique.

**Why this priority**: Evita estados fantasmas e melhora suporte/UX; necessário para resiliência operacional.

**Independent Test**: Simular sessão interrompida → interagir para ver prompt de recuperação → acionar `action:resume_session` e `recover:*` → testar `/help` e `help:<topic>` com UIService desligado → aplicar `/preferences simple` e verificar teclados.

**Acceptance Scenarios**:

1. **Given** há sessão órfã detectada, **When** o usuário recebe prompt e escolhe “Retomar”, **Then** o bot reativa a sessão, confirma retomada e restaura opções de gravação sem erro.
2. **Given** usuário solicita ajuda via `help:<topic>` com UIService indisponível, **When** o callback é processado, **Then** o bot entrega fallback seguro equivalente ao `/help` completo, sem exceções.
3. **Given** usuário envia `/preferences simple`, **When** o orquestrador atualiza preferências, **Then** as próximas respostas usam teclados/mensagens do modo simplificado sem regressões ou atributos faltantes.

---

### Edge Cases

- Comando digitado não documentado deve responder com mensagem padrão e sugestão de `/help`, sem lançar erro.
- Callback com parâmetro inválido (ex.: `page:abc`) deve registrar aviso interno e manter estado atual ao usuário.
- Busca semântica indisponível deve retornar mensagem amigável e oferecer retry ou retorno ao contexto anterior.
- Sessão órfã já tratada/ausente ao clicar em recuperar deve retornar “Nenhuma sessão órfã encontrada.” e limpar teclados de recuperação.
- Reinício do daemon durante fluxo de busca não pode deixar callbacks órfãos; próximos cliques devem ser reconhecidos ou substituídos por novo teclado coerente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Mapear todos os comandos expostos (/start, /status, /done, /finish, /transcripts, /search, /session, /help, /preferences, /process se exibido) a handlers do orquestrador com respostas em linguagem de produto.
- **FR-002**: Garantir roteamento explícito de callbacks inline (`action:*`, `help:*`, `recover:*`, `confirm:*`, `nav:*`, `retry:*`, `page:*`, `search:*`) para handlers correspondentes; nenhum callback gerado pela UI pode ficar órfão.
- **FR-003**: Callbacks de acknowledge (ex.: fechar ajuda, dismiss) devem registrar clique e encerrar teclado sem erros nem logs de “Unknown action”.
- **FR-004**: `/search <query>` e fluxo conversacional de busca devem usar a mesma rotina de busca semântica, retornando lista paginada com callbacks `search:select:<id>` e `page:<n>` consistentes.
- **FR-005**: Seleção de resultado (`search:select:<id>`) deve carregar sessão, mostrar resumo e oferecer ações de transcrição, processamento e reabertura conforme estado.
- **FR-006**: `/session <id-ou-nome>` deve localizar sessão por id ou nome amigável, atualizar contexto da interface e apresentar teclados adequados ao estado atual.
- **FR-007**: Recuperação de sessões órfãs deve detectar estados interrompidos após reinício e oferecer caminhos claros: retomar (`action:resume_session`), finalizar ou descartar, com mensagens confirmatórias.
- **FR-008**: Ajuda contextual deve mapear `help:<topic>` para ajuda específica do estado; na ausência do contexto/UIService, entregar fallback completo equivalente ao `/help` sem erro.
- **FR-009**: Preferências via `/preferences` devem permitir modo simplificado e refletir imediatamente em teclados/mensagens subsequentes, com persistência configurável fora do código.
- **FR-010**: Paginação de resultados deve validar parâmetros, manter estado consistente em caso de input inválido e oferecer feedback amigável em vez de erro técnico.
- **FR-011**: Observabilidade: registrar em logs estruturados callbacks inválidos, buscas indisponíveis, sessões órfãs detectadas e caminhos de recuperação executados, sem expor detalhes técnicos ao usuário.
- **FR-012**: Configuração externa: tokens, limites de paginação, toggles de UI, timeouts e endpoints de busca devem ser definidos via env/config; é proibido hardcoding no código ou mensagens.
- **FR-013**: Testabilidade: incluir testes automatizados que falham se algum comando/callback exposto não tiver handler mapeado ou se fluxos principais (gravar/finalizar, busca, recuperação, ajuda) quebram o contrato esperado.

### Key Entities *(include if feature involves data)*

- **Sessão**: identifica contexto de captura/processamento; atributos: id, nome amigável, estado (coletando, transcrevendo, transcrito, processando, processado, órfã), timestamps, preferências de UI associadas.
- **CallbackAction**: representa ação de teclado inline; atributos: tipo (action/help/recover/confirm/nav/retry/page/search), payload (id de sessão, página, tópico), estado de validação.
- **BuscaSemantica**: query em linguagem natural, resultados ordenados, paginação, seleção de item vinculada a sessão.
- **PreferenciasUI**: modo simplificado/normal, flags de exibição de teclados, armazenadas externamente (config/estado de usuário) e aplicadas nas respostas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos comandos documentados respondem sem “Unknown command” ou erro técnico em testes automatizados e manuais guiados.
- **SC-002**: 100% dos callbacks gerados pela UI são aceitos ou reconhecidos (incluindo no-ops), com zero “Unknown action” em logs durante suite de testes.
- **SC-003**: Fluxo gravação → transcrição → acesso a transcrições conclui em ≤4 interações de usuário e p95 ≤ 3 minutos (medido com mocks/timestamps), sem passos bloqueados.
- **SC-004**: `/search` retorna e abre sessão relevante em ≤2 interações após a lista inicial em 95% dos casos de teste; timeout de busca = 5s e page size = 5.
- **SC-005**: Sessões órfãs detectadas são apresentadas com opções de recuperação e tratadas corretamente em 100% dos cenários simulados de reinício.
- **SC-006**: Nenhum valor operacional sensível (tokens, limites, timeouts) permanece hardcoded após revisão; variáveis externas auditáveis são usadas em 100% dos pontos configuráveis.
