# Feature Specification: Semantic Session Search

**Feature Branch**: `006-semantic-session-search`  
**Created**: 2025-12-19  
**Status**: Draft  
**Input**: Artifact `02_specification.md` from session `2025-12-19_15-26-36`

**Constitution**: This spec MUST be compatible with `.specify/memory/constitution.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Search via Button (Priority: P1)

O usuário toca no botão [Buscar] na tela de resultados e é guiado a descrever a sessão que procura em linguagem natural. O sistema retorna resultados como botões inline clicáveis.

**Why this priority**: Esta é a funcionalidade core - materializa o botão [Buscar] que já existe na UI mas não está implementado. Cumpre o princípio constitucional "UX Baseada em Botões Inline".

**Independent Test**: Pode ser testado isoladamente - tocar [Buscar], digitar consulta, ver resultados como botões.

**Acceptance Scenarios**:

1. **Given** usuário na tela de resultados com botões visíveis, **When** toca em [Buscar], **Then** sistema solicita descrição da sessão em linguagem natural
2. **Given** sistema aguardando consulta de busca, **When** usuário digita "conversa sobre microsserviços", **Then** sistema processa via embedding e apresenta lista de botões inline com sessões ordenadas por similaridade
3. **Given** resultados de busca exibidos como botões, **When** usuário toca em uma sessão, **Then** sessão é restaurada como ativa e botões [Finalizar] [Status] [Ajuda] são exibidos

---

### User Story 2 - Session Restoration (Priority: P1)

O usuário seleciona uma sessão dos resultados de busca e ela é restaurada como contexto ativo, permitindo enviar novos áudios ou processar.

**Why this priority**: Sem restauração, a busca não tem valor. São funcionalidades interdependentes para o MVP.

**Independent Test**: Dado uma sessão encontrada, clicar nela deve restaurá-la e permitir ações imediatas.

**Acceptance Scenarios**:

1. **Given** resultados de busca com sessões, **When** usuário toca em um botão de sessão, **Then** sistema carrega sessão e define como ativa
2. **Given** sessão restaurada, **When** usuário envia novo áudio, **Then** áudio é adicionado à sessão restaurada (não cria nova sessão)
3. **Given** sessão restaurada, **When** usuário toca [Finalizar], **Then** sistema finaliza a sessão restaurada normalmente

---

### User Story 3 - No Results Handling (Priority: P2)

Quando nenhuma sessão corresponde à consulta, o sistema informa claramente e oferece opção de nova busca.

**Why this priority**: Importante para UX, mas não bloqueia o fluxo principal.

**Independent Test**: Buscar termo que não existe em nenhuma sessão e verificar mensagem + botões de recuperação.

**Acceptance Scenarios**:

1. **Given** sistema processando busca, **When** nenhuma sessão tem similaridade acima do limiar, **Then** exibe "Nenhuma sessão encontrada" + botões [Nova Busca] [Fechar]
2. **Given** mensagem de "nenhum resultado", **When** usuário toca [Nova Busca], **Then** sistema reinicia fluxo de busca

---

### User Story 4 - Corrupted Session Handling (Priority: P3)

Ao tentar restaurar uma sessão cujos arquivos estão corrompidos, o sistema informa o erro e oferece alternativas.

**Why this priority**: Edge case importante para robustez, mas não comum.

**Independent Test**: Simular sessão com arquivos ausentes e tentar restaurar.

**Acceptance Scenarios**:

1. **Given** resultados de busca incluindo sessão corrompida, **When** usuário toca no botão dessa sessão, **Then** sistema detecta corrupção e exibe erro + [Tentar Novamente] [Fechar]

---

### User Story 5 - Search Timeout (Priority: P3)

Se o usuário não digitar a consulta após tocar [Buscar], o sistema cancela automaticamente após período configurável.

**Why this priority**: Evita estado "travado", mas é edge case.

**Independent Test**: Tocar [Buscar] e aguardar sem digitar - sistema deve cancelar após timeout.

**Acceptance Scenarios**:

1. **Given** sistema aguardando consulta de busca, **When** 60 segundos se passam sem input, **Then** sistema cancela e envia "Busca cancelada por inatividade"

---

### Edge Cases

- **Consulta vazia**: Se usuário enviar texto vazio após [Buscar], sistema deve solicitar novamente
- **Muitos resultados**: Limitar a 5 resultados para não poluir a tela com botões
- **Sessão já ativa**: Se usuário buscar e selecionar a sessão que já está ativa, apenas confirmar (não duplicar)
- **Busca durante processamento**: Se houver transcrição em andamento, busca deve funcionar normalmente (operações independentes)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema DEVE apresentar botão [Buscar] funcional na tela de resultados (KeyboardType.RESULTS)
- **FR-002**: Sistema DEVE solicitar descrição em linguagem natural após toque em [Buscar]
- **FR-003**: Sistema DEVE processar consulta via modelo de embedding local (sentence-transformers)
- **FR-004**: Sistema DEVE apresentar resultados como botões inline (máximo 5 sessões)
- **FR-005**: Sistema DEVE exibir nome inteligível da sessão e score de similaridade em cada botão
- **FR-006**: Sistema DEVE restaurar sessão selecionada como contexto ativo
- **FR-007**: Sistema DEVE apresentar botões de sessão ativa após restauração
- **FR-008**: Sistema DEVE usar limiar configurável para similaridade mínima (default: 0.6)
- **FR-009**: Sistema DEVE cancelar busca após timeout configurável (default: 60s)
- **FR-010**: Sistema DEVE tratar sessões corrompidas com mensagem de erro clara

### Key Entities

- **SearchQuery**: Texto da consulta do usuário + chat_id + timestamp
- **SearchResult**: session_id + intelligible_name + similarity_score
- **ConversationalState**: Rastreia se chat está aguardando consulta de busca

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Usuário completa fluxo [Buscar] → consulta → seleção → restauração usando apenas toques em botões (zero digitação de comandos)
- **SC-002**: Sessão semanticamente relevante (contendo termos da consulta no transcript ou nome) aparece entre os 5 primeiros resultados em >80% das buscas
- **SC-003**: Tempo total do fluxo (toque em [Buscar] até sessão restaurada) < 10 segundos
- **SC-004**: Após restaurar sessão, envio de novo áudio funciona imediatamente sem erros
- **SC-005**: Busca por consulta sem correspondência exibe mensagem clara em <2 segundos

## Assumptions

- SearchService já implementado em `src/services/search/engine.py`
- EmbeddingIndexer já implementado em `src/services/search/indexer.py`
- UIService e keyboards já implementados em `src/services/telegram/`
- Botão [Buscar] já existe em KeyboardType.RESULTS mas não está conectado
