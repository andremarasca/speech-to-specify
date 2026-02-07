# Cláusulas Pétreas (Regras Fixas e Inegociáveis)

> **Princípio Fundamental:** LLMs performam melhor quando o sistema é **determinístico, explícito e modular**. Priorize a **navegabilidade** sobre a perfeição acadêmica, a **verificabilidade automática** sobre a elegância, e a **composição de partes simples** sobre a flexibilidade monolítica. Arquitetura para IA é uma **engenharia de restrições** que maximiza a previsibilidade do output.

Toda saída gerada contém e respeita estas regras em todos os projetos:

---

## I. Qualidade e Validação Automatizada

### 1. Excelência Estrutural Verificável

Qualidade de código é validada por **ferramentas automatizadas**, não por revisão humana. Obrigatório:

- `mypy --strict` passa sem erros (domínio e ports obrigatório; adapters pode relaxar para `--warn-unused-ignores`)
- Funções têm type hints completos
- Docstrings explicam **propósito** (não implementação)
- SOLID e Object Calisthenics são referências de design, não checklists de conformidade
- **Logs estruturados (JSON)** sempre que possível, seguindo schema canônico com `timestamp`, `context`, `level`, `error_code` e `message`

A IA não consegue manter disciplina linha-a-linha sem validação externa. **Ferramentas são a lei.**

#### Schema de Log Canônico

Todo log deve seguir este formato para garantir auditoria programática consistente:

```python
class LogEvent(TypedDict):
    timestamp: str      # ISO 8601
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    context: str        # Módulo/função origem
    error_code: str | None
    message: str
    # Campos obrigatórios para rastreio de consistência (ver Cláusula 25)
    fallback_activated: bool | None
    data_consistency_risk: Literal["NONE", "LOW", "HIGH"] | None
```

### 2. Verificação de Execução Obrigatória

Toda modificação de código requer, além da execução dos testes unitários:

1. **Execução completa** do aplicativo (backend e frontend, se aplicável)
2. **Monitoramento ativo** por pelo menos 1 minuto
3. **Verificação de logs** e arquivos de estado para garantir ausência de erros silenciosos
4. **Leitura das últimas 50 linhas** de `logs/last_run.log` (quando disponível) antes de declarar tarefa concluída

**Ao finalizar qualquer tarefa de codificação**, incluir seção:

```markdown
## ✅ Checklist de Verificação

- [ ] Testes unitários passaram
- [ ] Executou o código (backend e frontend)
- [ ] Monitorou a execução por pelo menos 1 minuto
- [ ] Verificou logs e arquivos de estado para garantir que não há erros silenciosos
- [ ] Confirmou **ausência** de `FALLBACK_ACTIVATED` ou `data_consistency_risk: HIGH` nos logs
- [ ] Scripts .bat testados (se modificados)
```

> **Nota:** O checklist deve ser verificável por artefatos sempre que possível (logs gerados, outputs esperados), não apenas declarativo.

### 3. Integridade de Testes

- Sucesso é **binário** (se um teste falha, a tarefa falha)
- Testes validam **comportamento e lógica de negócio**, não parâmetros hardcoded
- Refatorações preservam testes enquanto a lógica permanecer a mesma
- Funções puras do domínio têm **cobertura obrigatória**
- Testes seguem padrão **Given-When-Then** para clareza semântica
- **Testes como âncora de contexto:** Ao gerar código, a IA deve priorizar leitura e alinhamento com testes existentes antes de criar novas implementações

---

## II. Arquitetura e Estrutura

### 4. Arquitetura Hexagonal Obrigatória

O sistema adota **Ports & Adapters** como padrão arquitetural inegociável:

- O **domínio** (regras de negócio puras) não possui dependências externas
- **Ports** definem contratos abstratos via `Protocol` (Python) ou interfaces equivalentes
- **Adapters** implementam os Ports e são substituíveis sem afetar o domínio
- Nenhum código de domínio importa diretamente implementações concretas de I/O, persistência ou serviços externos

### 5. Estrutura de Diretórios Canônica

A estrutura de pastas segue convenção **rígida e previsível**. Novos módulos seguem o padrão existente. A IA não decide estrutura, **segue convenção**:

```
src/
├── domain/           # Regras de negócio puras (funções puras, sem I/O)
│   ├── entities/     # Objetos de domínio
│   ├── value_objects/# Tipos imutáveis
│   ├── services/     # Lógica de domínio
│   └── errors/       # Erros tipados de domínio
├── ports/            # Contratos (Protocols)
│   ├── inbound/      # Casos de uso (o que o sistema FAZ)
│   └── outbound/     # Dependências externas (o que o sistema USA)
├── adapters/         # Implementações concretas
│   ├── inbound/      # Controllers, CLI, handlers
│   └── outbound/     # Repositories, APIs, gateways
├── config/           # Composição e DI (container/factory)
└── shared/           # Utilitários compartilhados (Result, tipos base)
```

**Regras de importação (validadas por ferramentas):**
- `domain/` → não importa nada externo
- `ports/` → importa apenas `domain/`
- `adapters/` → importa `ports/` e `domain/`
- `config/` → importa tudo (ponto de composição)
- **Importação circular é proibida.** Se A precisa de B e B precisa de A, extraia a interface para um Port ou mova a lógica comum para Domain.

### 6. Protocol-First Design

Toda dependência externa (LLM, STT, TTS, storage, APIs) possui um **Protocol definido ANTES** de qualquer implementação:

- O Protocol é o **contrato**; implementações são detalhes
- Novos adapters são adicionados **sem modificar código existente**
- O Agente Executor **não cria implementações sem Protocol prévio**
- Protocols são **minimalistas**: métodos pequenos, sem defaults, sem comportamento implícito

```python
# ✅ Correto: métodos atômicos
class OrderRepository(Protocol):
    def create(self, order: Order) -> None: ...
    def update(self, order: Order) -> None: ...

# ❌ Incorreto: semântica oculta
class OrderRepository(Protocol):
    def save(self, order: Order, upsert: bool = True) -> None: ...
```

### 7. Functional Core, Imperative Shell

- Lógica de domínio é implementada como **funções puras** sempre que possível (mesma entrada produz mesma saída, sem side effects)
- I/O e side effects são **isolados na camada de adapters** (shell imperativo)
- Funções puras são a **unidade primária de teste**
- **Complexidade ciclomática máxima: 7.** Condicionais aninhadas profundas devem ser extraídas em funções nomeadas (buscar < 5; acima de 10 requer revisão obrigatória)

### 8. Granularidade de Arquivos

Cada arquivo `.py` exporta no máximo **uma classe pública** ou um conjunto coeso de funções relacionadas:

- Arquivos com mais de **200 linhas** são candidatos a split (150-250 é aceitável se coeso)
- A IA opera melhor com **unidades atômicas**
- Um arquivo, uma responsabilidade exportável
- **Critério de coesão:** se os testes sempre importam o mesmo conjunto de funções juntas, o arquivo está coeso

```
❌ Ruim: services/user_service.py (500+ linhas)
✅ Bom:  services/user/create_user.py (~50-100 linhas)
         services/user/authenticate_user.py
```

---

## III. Tipos, Dados e Validação

### 9. Imutabilidade por Padrão

- Objetos de domínio são **imutáveis** (`frozen=True` em dataclasses)
- Mutação ocorre apenas em adapters de estado (repositories)
- Elimina bugs de estado compartilhado e facilita raciocínio sobre fluxos

```python
@dataclass(frozen=True)
class OrderItem:
    product_id: str
    quantity: PositiveInt
    price: Decimal
```

### 10. Erros como Tipos de Domínio (Result Pattern)

Erros de negócio são **Value Objects ou Enums tipados**, nunca exceções genéricas:

```python
@dataclass(frozen=True)
class Success(Generic[T]):
    value: T

@dataclass(frozen=True)
class Failure(Generic[E]):
    error: E

Result = Union[Success[T], Failure[E]]

# Uso
def create_order(cart: Cart) -> Result[Order, OrderCreationError]:
    if not cart.items:
        return Failure(OrderCreationError.EMPTY_CART)
    return Success(Order(...))
```

O sistema de tipos **obriga** a tratar o erro. Fluxo previsível, sem surpresas.

### 11. Validação Semântica e Normalização Tipada

Todo dado de entrada tem tipo **validado explicitamente** antes de uso no domínio:

- Dados inválidos invalidam execução ou disparam normalização explícita, **nunca coerção implícita**
- Pontos de entrada definem contratos formais (types, schemas, value objects)
- Adapters validam e normalizam; domínio assume correção total
- Conversões seguem **semântica do dado**:
  - string numérica → int (se cardinalidade)
  - timestamp → datetime timezone-aware
  - float monetário → Decimal
- Casts silenciosos ou dependência de comportamento do runtime são **proibidos**
- Testes de contrato de entrada são **mandatórios**

---

## IV. Configuração e Dependências

### 12. Configuração Externa e Zero Hardcoding

É **terminantemente proibido** o uso de valores literais ou parâmetros hardcoded no código:

- URLs, credenciais, portas, timeouts, limites → arquivos de configuração (`.env`)
- O Agente Executor extrai todo parâmetro configurável para o ambiente
- **`.env` e `.env.example` devem estar sempre sincronizados**: toda variável em `.env` deve existir em `.env.example` (com valor de exemplo) e vice-versa
- Violações desta regra **invalidam a entrega**

### 13. Injeção de Dependências Explícita

- Componentes recebem suas dependências via **construtor ou parâmetro**, nunca instanciam internamente
- Isso garante testabilidade e substituição de implementações
- A composição ocorre em uma **camada de configuração dedicada** (container/factory)

```python
@dataclass(frozen=True)
class Container:
    """Ponto único de composição de dependências."""
    llm: LLMGateway
    storage: StorageGateway
    
def create_production_container(settings: Settings) -> Container:
    return Container(
        llm=OpenAIAdapter(api_key=settings.openai_key),
        storage=FileStorageAdapter(base_path=settings.storage_path),
    )
```

---

## V. Contratos e Documentação

### 14. Contratos Antes de Comportamento

O Agente Executor recebe **contratos** (Protocols, interfaces, tipos) como entrada primária:

- Prompts que descrevem comportamento sem contrato prévio são rejeitados ou convertidos para contract-first
- A IA **implementa contratos**, não inventa interfaces
- Código gerado sem contrato prévio é tratado como **rascunho**, não como entrega

**Exceção - Fase de Descoberta:** Para exploração de APIs externas novas, é permitido criar código "sujo" em `sandbox/` ou `explorations/`, marcado como descartável e **nunca integrado ao `src/`**. Este código serve apenas como especificação informal para criar o Protocol real.

### 15. Glossário de Linguagem Ubíqua

Um conceito possui **um único nome canônico** em todo o sistema:

- Não misturar `User`, `Customer`, `Account` para o mesmo conceito
- Não misturar `Repository`, `Gateway`, `Storage` arbitrariamente
- Manter arquivo `docs/glossary.md` com definições fechadas
- **Alternativa:** Manter glossário como código em `src/shared/glossary.py` com constantes/Enums documentados

### 16. Tutorial de Extensibilidade Obrigatório

Toda funcionalidade nova ou modificada que introduza comportamento configurável, heurístico ou passível de personalização futura acompanha um **tutorial técnico explícito** documentando:

1. Finalidade da funcionalidade
2. Localização da lógica
3. Pontos formais de extensão
4. Procedimento de alteração
5. O que **NÃO** deve ser modificado

A ausência desse tutorial caracteriza a funcionalidade como **arquiteturalmente incompleta**, configurando dívida técnica ativa.

**Formato canônico do tutorial:**
```markdown
## Extending [Feature Name]

### Purpose
[O que esta funcionalidade faz, em uma frase]

### Location
- Main logic: `src/domain/services/[feature].py`
- Port: `src/ports/outbound/[feature]_port.py`
- Adapter(s): `src/adapters/outbound/[implementation]/`

### To Add New [Variation]:
1. Implement `[Variation]Port`
2. Create `[Variation]Adapter`
3. Register in `config/container.py`
4. Update `.env.example` with new config vars

### To Modify Behavior:
- Configuration: Edit `config/settings.py`
- Business rules: Edit domain service (pure functions only)
- I/O behavior: Edit adapter

### What NOT to modify:
- [Lista arquivos que não devem ser alterados]
```

---

## VI. Execução e Acessibilidade

### 17. Scripts de Execução (.bat) Obrigatórios

Todo projeto mantém uma pasta `scripts/` com arquivos `.bat` (Windows) para operações essenciais. O objetivo é **não obrigar o usuário a consultar README.md ou memorizar comandos**:

```
scripts/
├── run.bat              # Executa o aplicativo principal
├── run_dev.bat          # Executa em modo desenvolvimento
├── run_tests.bat        # Executa todos os testes
├── run_mypy.bat         # Valida tipos
├── install.bat          # Instala dependências
├── setup_env.bat        # Configura ambiente virtual
├── check_all.bat        # Roda mypy + pytest + lint de uma vez
└── [feature]_*.bat      # Variações por funcionalidade
```

**Regras:**
- Scripts .bat são a **porta de entrada** ao software desenvolvido
- Qualquer adição de funcionalidade que couber novos .bat com variações de inicialização deve criá-los
- Mudanças estruturais que precisem ajustar os .bat atuais **devem atualizá-los**
- **Todos os .bat devem ser testados** após qualquer modificação
- Scripts devem ser **autoexplicativos** (incluir `echo` descrevendo o que fazem)
- **Encoding UTF-8 e line endings consistentes** (preferir LF; CRLF apenas se necessário para Windows)

**Documentação mínima de cada .bat:**
```batch
@echo off
REM ================================================
REM Entradas esperadas: [variáveis de ambiente, argumentos]
REM Outputs esperados: [arquivos gerados, códigos de saída]
REM Efeitos colaterais: [processos iniciados, arquivos modificados]
REM ================================================
```

---

## VII. Autoconhecimento e Limitações da IA

### 18. Reconhecimento de Limitações do Agente Executor

O Agente Executor (IA) reconhece que:

- **Não mantém modelo mental persistente** do sistema
- **Não tem consciência do custo de manutenção futura**
- **Tende a otimizar localmente**

Portanto:

- **Decisões arquiteturais são humanas** (IA não sugere estrutura, segue convenção)
- **Validação é por ferramentas** (IA não revisa próprio código)
- **Prompts devem ser determinísticos** com contratos explícitos (IA não debate, executa)

### 19. Fluxo de Geração Determinístico

Ao implementar funcionalidades, seguir ordem estrita:

0. **Planejamento:** Emitir plano de execução listando arquivos a criar/modificar e como respeitam as cláusulas pétreas
0.5. **Análise de Impacto (Impact Graph):** Antes de qualquer código, listar TODOS os arquivos que importam os módulos afetados e classificar impacto: `[QUEBRA CONTRATO]` ou `[INTERNO]` (ver Cláusula 26)
1. Verificar **glossário** para garantir consistência de termos
2. Identificar/criar **Protocol** (Port) necessário
3. Criar **testes** baseados no contrato (que falham inicialmente)
4. Implementar **lógica de domínio** (funções puras)
5. Implementar **Adapter** se necessário
6. Validar com **mypy** e **pytest**
7. Atualizar **container.py** se nova dependência
8. Criar/atualizar **tutorial de extensibilidade**
9. Atualizar **scripts .bat** se aplicável
10. **Executar e monitorar** aplicação completa

### 20. YAGNI Rigoroso (Proibição de Abstrações Prematuras)

- **Não criar** interfaces/Protocols "apenas porque pode precisar no futuro"
- Protocol só é criado quando existe ou está sendo implementado **imediatamente** um adapter
- **Proibido** criar "base classes", "abstract services" ou "helpers genéricos" sem uso concreto atual
- Quando em dúvida: implemente primeiro como função concreta, extraia Protocol só na segunda implementação
- A IA tende a over-engineer; esta cláusula força simplicidade

### 21. Convenções Determinísticas de Nomenclatura

Para eliminar ambiguidade e facilitar navegação:

- **Ports:** `[Entity][Action]Port` (ex: `UserRepositoryPort`, `EmailSenderPort`)
- **Adapters:** `[Tech][Entity]Adapter` (ex: `PostgresUserAdapter`, `SendGridEmailAdapter`)
- **Services de domínio:** `[action]_[entity].py` (ex: `create_user.py`, `validate_order.py`)
- **Use Cases:** `[Verbo][Entidade]UseCase` com método único `execute()` (ex: `CreateOrderUseCase`)
- **Value Objects:** substantivos adjetivados (ex: `EmailAddress`, `PositiveInteger`)
- **Erros:** `[Domain][ErrorType]Error` (ex: `UserNotFoundError`, `PaymentFailedError`)

### 22. Proibição de Magia e Metaprogramação

LLMs quebram completamente com lógica implícita invisível. É **terminantemente proibido**:

- Metaprogramação (metaclasses, `__new__` com lógica complexa)
- Decorators com lógica implícita de transformação (decorators simples de logging são permitidos)
- Magic methods fora de Value Objects e dataclasses
- Reflection para alterar comportamento em runtime
- Monkey patching
- Import-time side effects

**Regra:** Se o comportamento não é óbvio lendo o código linha a linha, está proibido.

### 23. Mapa de Contexto do Projeto

Para projetos com mais de 20 arquivos, manter um **mapa de navegação** atualizado:

- Arquivo `docs/map.md` descrevendo árvore de arquivos e responsabilidade resumida de cada módulo
- Toda criação/deleção de arquivo deve atualizar o mapa
- O mapa serve como "GPS" para a IA em cada novo prompt

**Formato sugerido:**
```markdown
## Mapa do Projeto

### src/domain/
- `entities/user.py` - Entidade User com validações de domínio
- `services/create_user.py` - Lógica pura de criação de usuário

### src/adapters/outbound/
- `postgres_user_adapter.py` - Persistência de User em PostgreSQL
```

### 24. Erros com Semântica Formal

Além de tipados, erros de domínio devem seguir um contrato semântico mínimo:

```python
class DomainError(Protocol):
    @property
    def code(self) -> str: ...
    @property
    def message(self) -> str: ...
```

Isso permite:
- Logs automáticos padronizados
- Mapeamento determinístico para HTTP status codes ou respostas CLI
- Menos if/else em adapters de apresentação

---

## VIII. Integridade em Transições e Migrações

### 25. Integridade Radical em Transições (Strict Mode)

Durante refatorações estruturais ou migrações (ex: troca de banco, mudança de API), a integridade dos dados tem **prioridade absoluta** sobre a disponibilidade.

- **Modo Estrito:** O sistema deve suportar uma flag `STRICT_ARCHITECTURE_MODE=true` (via `.env`). Quando ativa:
  - Falhas em sistemas secundários (ex: dual-write) disparam **exceções bloqueantes** (crash), nunca warnings
  - Discrepâncias de contrato interrompem a execução
- **Proibição de Degradação Silenciosa:** É proibido capturar exceções críticas e logar apenas como `WARNING` sem interromper o fluxo, a menos que explicitamente documentado como estratégia de resiliência em produção estável
- **Logs de Pânico:** Se um fallback for inevitável, deve ser logado com nível `ERROR` e metadados obrigatórios:

```python
# Formato obrigatório para fallbacks
logger.error(
    "Fallback ativado",
    extra={
        "fallback_activated": True,
        "data_consistency_risk": "HIGH",
        "risk": "DATA_CONSISTENCY",
        "action": "FALLBACK_TRIGGERED",
        "original_error": str(exception),
    },
)
```

> **Regra:** `try...except...warning` em operações de escrita é **terminantemente proibido** quando `STRICT_ARCHITECTURE_MODE=true`.

### 26. Rastreabilidade de Dependências (Impact Graph)

Antes de qualquer alteração em **Interfaces, Protocols ou Schemas de Dados**, a IA deve gerar um **Grafo de Impacto** explícito:

1. **Listar Produtor:** O arquivo que será modificado
2. **Listar Consumidores Diretos:** Arquivos que importam o produtor
3. **Listar Consumidores Transitivos:** Arquivos que dependem do fluxo, mesmo sem import direto
4. **Checklist de Propagação:** A tarefa só é concluída quando todos os arquivos listados foram validados ou refatorados

> *A IA é proibida de assumir que uma mudança de contrato é isolada. Se a assinatura muda, todos os consumidores devem ser inspecionados.*

**Formato obrigatório do Impact Graph:**
```markdown
## Impact Graph — [Descrição da Mudança]

### Produtor
- `src/ports/outbound/repository_port.py` — Método `save()` alterado

### Consumidores Diretos
- `src/adapters/outbound/postgres_adapter.py` — [QUEBRA CONTRATO]
- `src/adapters/outbound/file_adapter.py` — [QUEBRA CONTRATO]

### Consumidores Transitivos
- `src/config/container.py` — [INTERNO] (composição)
- `scripts/run_producer.py` — [INTERNO] (invocação)

### Status de Propagação
- [ ] Todos os consumidores validados
- [ ] Testes de contrato atualizados
- [ ] mypy passa sem erros
```

### 27. Definition of Done para Migrações

Migrações de infraestrutura não são "troca de código", são **garantia de equivalência**.

- **Dualidade de Testes:** Obrigatória a execução de **Testes de Contrato** agnósticos que validam tanto a implementação legada quanto a nova
- **Prova de Equivalência:** A migração só termina quando a suite de testes passa **verde** para ambos os adapters simultaneamente
- **Limpeza Separada:** A remoção do código antigo é uma etapa separada, executada apenas após a validação em produção (stage/prod) do novo código
- **Proibição de Migração Parcial:** Não é permitido declarar migração completa enquanto existirem caminhos de execução que ainda dependam do adapter legado sem cobertura de testes

```python
# Exemplo: teste de contrato agnóstico para migrações
import pytest
from src.ports.outbound.storage_port import StoragePort

@pytest.fixture(params=["legacy_adapter", "new_adapter"])
def storage(request) -> StoragePort:
    if request.param == "legacy_adapter":
        return LegacyFileStorage()
    return NewCloudStorage()

def test_save_and_retrieve(storage: StoragePort) -> None:
    """Deve produzir resultado idêntico em ambos os adapters."""
    storage.save("key", "value")
    assert storage.retrieve("key") == "value"
```

---

## Resumo: O que Maximiza Sucesso da IA

| Prática                         | Impacto                          |
| ------------------------------- | -------------------------------- |
| Arquivos pequenos (<200 linhas) | IA lê contexto completo          |
| Estrutura previsível            | IA navega sem "descobrir"        |
| Protocols como spec             | IA sabe o que implementar        |
| Result pattern                  | Fluxos explícitos, sem surpresas |
| Testes como âncora              | IA aprende por exemplo           |
| Composition Root                | Ponto único de mudança           |
| Imutabilidade                   | Menos estados para rastrear      |
| Scripts .bat                    | Execução sem fricção             |
| Verificação pós-código          | Bugs detectados em runtime       |
| YAGNI rigoroso                  | Evita over-engineering           |
| Nomenclatura determinística     | Zero ambiguidade                 |
| Logs estruturados               | Auditoria automática             |
| Proibição de magia              | Comportamento sempre explícito   |
| Mapa de contexto                | IA navega sem "descobrir"        |
| .env sincronizado               | Configuração sempre completa     |
| Strict Mode em transições       | Falhas nunca são silenciosas     |
| Impact Graph obrigatório        | Migrações sem efeitos colaterais |
| DoD para migrações              | Equivalência comprovada          |

---

## Arquivos Âncora (Read-Only para IA)

Os seguintes arquivos são **referência**, não devem ser modificados pela IA sem aprovação explícita:

- `prompts/unalterable_clauses.md` (este arquivo)
- `prompts/constitution.md`
- `docs/glossary.md`
- `docs/map.md`

Estes servem como **âncoras cognitivas** para manter consistência ao longo do tempo.

---

**Arquitetura boa para IA é: previsível 📐 · repetitiva 🔁 · restritiva 🔒 · semanticamente explícita 🧠 · verificável por artefatos ✅**