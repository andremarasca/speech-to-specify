# Feature Specification: Contextual Oracle Feedback

**Feature Branch**: `007-contextual-oracle-feedback`  
**Created**: 2025-12-20  
**Status**: Draft  
**Input**: User description: "Sistema de feedback contextual com oráculos dinâmicos - personalidades LLM carregadas de arquivos markdown com persistência de histórico de sessão"

**Constitution**: This spec MUST be compatible with `.specify/memory/constitution.md`.

**Constitution Gates (Telegram Interface)**:
- Mapear e versionar conceitualmente todos os comandos/callbacks, sem handlers ausentes
- Projetar estrutura em linha com SOLID/Object Calisthenics, evitando if/else ad hoc
- Garantir testes automatizados cobrindo contratos de interface; qualquer falha bloqueia entrega
- Planejar observabilidade e caminhos de recuperação (anomalies, sessões órfãs, retomada/finalização)
- Definir toda configuração como externa (env/config); hardcoding é proibido
- Assegurar testabilidade independente de cada fluxo/teclado, sem depender de testes manuais

## Contexto e Problema

O problema central é a natureza linear e volátil dos brainstorms por áudio. O usuário gera sequências de ideias, mas carece de um mecanismo imediato para desafiar ou expandir esses pensamentos com base em contextos anteriores. O **Oráculo de Ideias** transforma o monólogo em um diálogo produtivo e contextualizado, onde o feedback é cumulativo e integrado à memória da sessão.

**Premissas de Design:**
- Personalidades (oráculos) são definidas via arquivos markdown em diretório configurável
- Cada personalidade gera automaticamente um botão na interface do Telegram
- O título do markdown (primeira linha) define o nome exibido no botão
- Respostas de LLM são persistidas e podem ser incluídas no contexto de interações futuras
- A inclusão de histórico de LLM no contexto é configurável pelo usuário

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Solicitar Feedback de Oráculo (Priority: P1)

Como usuário do sistema de brainstorm, após enviar um ou mais áudios e ver suas transcrições, quero selecionar uma personalidade de oráculo (ex: "Cético", "Visionário") via botão clicável para receber feedback contextualizado baseado em todo o conteúdo da minha sessão.

**Why this priority**: Esta é a funcionalidade central que entrega o valor primário do produto — transformar monólogo em diálogo produtivo. Sem ela, o sistema é apenas um transcritor.

**Independent Test**: Pode ser testado enviando um áudio de teste, aguardando transcrição, clicando no botão de um oráculo e verificando que a resposta considera o conteúdo transcrito.

**Acceptance Scenarios**:

1. **Given** uma sessão ativa com pelo menos uma transcrição disponível, **When** o usuário clica no botão de um oráculo (ex: "Cético"), **Then** o sistema envia as transcrições concatenadas junto ao prompt da personalidade para a LLM e exibe a resposta no Telegram.

2. **Given** múltiplas transcrições na sessão (áudios 1, 2 e 3), **When** o usuário solicita feedback do oráculo, **Then** todas as transcrições são incluídas no contexto na ordem cronológica de gravação.

3. **Given** o usuário recebe resposta de um oráculo, **When** a resposta é exibida, **Then** ela é automaticamente persistida no histórico da sessão para uso futuro.

---

### User Story 2 - Botões Dinâmicos de Personalidades (Priority: P1)

Como usuário, quero ver botões de oráculos gerados automaticamente a partir dos arquivos de personalidade existentes no diretório configurado, sem necessidade de alteração no código quando novas personalidades são adicionadas.

**Why this priority**: Essencial para a arquitetura plugin-first definida na constituição. Permite evolução orgânica do ecossistema de oráculos.

**Independent Test**: Pode ser testado adicionando um novo arquivo `.md` no diretório de personalidades e verificando que um novo botão aparece na próxima interação.

**Acceptance Scenarios**:

1. **Given** três arquivos de personalidade no diretório (`cetico.md`, `visionario.md`, `otimista.md`), **When** o sistema renderiza a interface após uma transcrição, **Then** três botões são exibidos com os títulos extraídos da primeira linha de cada arquivo.

2. **Given** um arquivo de personalidade com título "# Cético Radical", **When** o botão é renderizado, **Then** o texto exibido é "Cético Radical" (sem o símbolo `#`).

3. **Given** um novo arquivo de personalidade é adicionado ao diretório, **When** o usuário interage com o sistema, **Then** o novo botão aparece automaticamente sem necessidade de reiniciar ou recompilar.

4. **Given** um arquivo de personalidade é removido do diretório, **When** o usuário interage com o sistema, **Then** o botão correspondente não é mais exibido.

---

### User Story 3 - Feedback em Espiral com Histórico de LLM (Priority: P2)

Como usuário avançado, quero que minhas interações subsequentes com oráculos considerem não apenas as transcrições, mas também as respostas anteriores de LLM, criando uma espiral de refinamento de ideias.

**Why this priority**: Diferencial competitivo que transforma a ferramenta em verdadeiro "parceiro de pensamento". Depende das stories P1 estarem funcionais.

**Independent Test**: Pode ser testado solicitando feedback de um oráculo, depois de outro oráculo, e verificando que a segunda resposta referencia ou considera a primeira.

**Acceptance Scenarios**:

1. **Given** a opção de incluir histórico de LLM está ativada e existe uma resposta anterior do "Cético", **When** o usuário solicita feedback do "Otimista", **Then** o contexto enviado inclui transcrições + resposta do Cético concatenados linearmente.

2. **Given** três interações na sessão (áudio1, resposta_cetico, áudio2), **When** o usuário solicita feedback do Visionário, **Then** o contexto é montado na ordem: [áudio1_transcr] + [resposta_cetico] + [áudio2_transcr].

3. **Given** múltiplas respostas de LLM na sessão, **When** todas são concatenadas no contexto, **Then** cada resposta é claramente delimitada com identificação do oráculo que a gerou.

---

### User Story 4 - Configuração de Inclusão de Histórico LLM (Priority: P2)

Como usuário, quero poder ativar ou desativar a inclusão de respostas anteriores de LLM no contexto de novas solicitações, para controlar se quero um feedback "fresco" ou contextualizado.

**Why this priority**: Dá controle ao usuário sobre seu fluxo criativo, respeitando a soberania da agência do usuário definida na constituição.

**Independent Test**: Pode ser testado alternando a configuração e verificando que o comportamento do contexto muda conforme esperado.

**Acceptance Scenarios**:

1. **Given** a configuração de histórico LLM está desativada, **When** o usuário solicita feedback, **Then** apenas as transcrições de áudio são incluídas no contexto (respostas anteriores de LLM são ignoradas).

2. **Given** a configuração de histórico LLM está ativada, **When** o usuário solicita feedback, **Then** transcrições e respostas de LLM são incluídas no contexto.

3. **Given** o usuário acessa o menu de configurações, **When** altera a opção de histórico LLM, **Then** a alteração é persistida e aplicada imediatamente nas próximas solicitações.

---

### User Story 5 - Resiliência a Falhas (Priority: P3)

Como usuário, quero que o sistema continue funcionando de forma degradada quando subsistemas falham, preservando o que já foi produzido e alertando sobre limitações temporárias.

**Why this priority**: Garante experiência robusta, mas não bloqueia o valor principal das stories P1/P2.

**Independent Test**: Pode ser testado simulando falhas de componentes e verificando comportamento de degradação graceful.

**Acceptance Scenarios**:

1. **Given** uma falha no serviço de persistência de histórico, **When** o usuário continua gravando áudios, **Then** o sistema opera em "modo de memória volátil" com alerta visível ao usuário.

2. **Given** a LLM retorna erro de timeout, **When** o usuário tenta novamente, **Then** o histórico anterior permanece intacto e disponível para a nova tentativa.

3. **Given** um arquivo de personalidade está corrompido (malformado), **When** o sistema carrega os botões, **Then** o arquivo corrompido é ignorado e os demais botões são exibidos normalmente.

4. **Given** falha na gravação de um áudio específico, **When** o usuário visualiza a sessão, **Then** as respostas de LLM já armazenadas permanecem acessíveis (isolamento de erros entrada/saída).

---

### Edge Cases

- **Placeholder ausente no prompt**: O que acontece se o arquivo de personalidade não contiver placeholder para inserção de contexto? *Assunção: O sistema utiliza um placeholder padrão configurável (ex: `{{CONTEXT}}`).*
- **Diretório de personalidades vazio**: O que acontece se não existirem arquivos de personalidade? *Assunção: Uma mensagem informativa é exibida indicando que nenhum oráculo está disponível.*
- **Callback data excede limite do Telegram**: Nomes de arquivos muito longos podem exceder o limite de 64 bytes do callback_data. *Assunção: Arquivos com caminhos longos são ignorados com log de warning.*
- **Sessão sem transcrições**: O que acontece se o usuário clicar em um oráculo antes de enviar qualquer áudio? *Assunção: Mensagem informativa indicando que não há conteúdo para analisar.*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE carregar arquivos de personalidade de um diretório configurável via variável de ambiente ou arquivo de configuração.
- **FR-002**: O sistema DEVE extrair o título da personalidade da primeira linha do arquivo markdown (removendo o símbolo `#` se presente).
- **FR-003**: O sistema DEVE gerar botões inline dinâmicos para cada personalidade válida encontrada no diretório.
- **FR-004**: O sistema DEVE concatenar todas as transcrições da sessão ativa ao solicitar feedback de um oráculo.
- **FR-005**: O sistema DEVE inserir o contexto concatenado no placeholder definido no arquivo de personalidade.
- **FR-006**: O sistema DEVE persistir cada resposta de LLM em uma subpasta dedicada da sessão ativa.
- **FR-007**: O sistema DEVE permitir configuração de inclusão/exclusão de histórico de LLM no contexto.
- **FR-008**: O sistema DEVE concatenar transcrições e respostas de LLM em ordem cronológica quando a opção estiver ativada.
- **FR-009**: O sistema DEVE identificar claramente a origem de cada bloco no contexto (transcrição vs resposta de oráculo específico).
- **FR-010**: O sistema DEVE ignorar arquivos de personalidade corrompidos ou inválidos, logando warnings sem interromper operação.
- **FR-011**: O sistema DEVE exibir mensagem informativa quando o diretório de personalidades estiver vazio.
- **FR-012**: O sistema DEVE exibir mensagem informativa quando não houver transcrições para analisar.
- **FR-013**: O sistema DEVE alertar o usuário quando operando em modo de memória volátil (falha de persistência).

### Key Entities

- **Personalidade (Oracle)**: Representa uma persona de IA definida por um arquivo markdown. Atributos: nome (título), conteúdo do prompt, placeholder de contexto.
- **Sessão (Session)**: Agrupa todas as interações do usuário em um período. Contém transcrições de áudio e respostas de LLM ordenadas cronologicamente.
- **Transcrição (Transcript)**: Texto resultante da conversão de um áudio. Possui timestamp e referência ao áudio original.
- **Resposta de Oráculo (OracleResponse)**: Texto gerado por uma LLM em resposta a uma solicitação. Possui timestamp, identificação do oráculo usado e referência ao contexto que gerou.
- **Contexto (Context)**: Bloco de texto montado dinamicamente combinando transcrições e (opcionalmente) respostas anteriores de LLM para envio ao modelo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Após cada transcrição, os botões de oráculos disponíveis são exibidos em menos de 200ms (latência imperceptível).
- **SC-002**: A n-ésima resposta de oráculo demonstra compreensão do conteúdo das transcrições e respostas anteriores (verificável via referências explícitas ao conteúdo prévio).
- **SC-003**: Adicionar um novo arquivo de personalidade no diretório configurado resulta em novo botão disponível na próxima interação, sem alteração de código ou reinício do sistema.
- **SC-004**: Em caso de falha de persistência, o sistema continua operacional com alerta visível e degradação graceful.
- **SC-005**: Usuários realizam em média 3 ou mais interações com oráculos diferentes na mesma sessão (indicador de engajamento profundo).
- **SC-006**: 100% das respostas de LLM são persistidas com sucesso quando o subsistema de armazenamento está operacional.

## Assumptions

- O diretório de personalidades utiliza um placeholder padrão `{{CONTEXT}}` para inserção de contexto, configurável via ambiente.
- Arquivos de personalidade são arquivos markdown (.md) com título na primeira linha.
- A persistência de respostas de LLM utiliza o mesmo mecanismo de armazenamento das transcrições (sistema de arquivos da sessão).
- O limite de 64 bytes do callback_data do Telegram é respeitado truncando ou ignorando caminhos muito longos.
- A ordem cronológica é determinada pelo timestamp de criação do conteúdo (áudio ou resposta de LLM).
