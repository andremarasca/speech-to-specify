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

#### Pipeline de Enforcement Obrigatório

Validação automática deve ser executada em pelo menos **um** destes pontos:

1. **Pre-commit hook** (preferido para feedback rápido)
2. **CI pipeline** (obrigatório se o projeto tem CI)
3. **Script `scripts/check_all.py`** (mínimo aceitável — orquestrador portável fornecido em `scripts/`)

O orquestrador `scripts/check_all.py` executa em sequência: **mypy → pytest → check_imports → check_file_sizes → generate_map → validate_env → check_explorations**. Wrappers `check_all.bat` (Windows) e `check_all.sh` (Unix) são fornecidos para conveniência.

```bash
# Execução completa
python scripts/check_all.py

# Pular testes (apenas validação estrutural)
python scripts/check_all.py --skip-tests --skip-mypy

# Continuar mesmo após falha (para ver todas as violações)
python scripts/check_all.py --continue
```

Para dependências externas sem stubs (`py.typed`):
- Usar `# type: ignore[import-untyped]` com comentário explicativo
- Manter lista de exceções em `mypy.ini` sob seção `[mypy-<package>]`
- Exceções devem ser revisadas a cada release

> **Regra:** Se o enforcement não está automatizado, não é enforcement — é sugestão.

#### Schema de Log Canônico

Todo log deve seguir este formato para garantir auditoria programática consistente:

```python
class LogEvent(TypedDict):
    timestamp: str      # ISO 8601
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    context: str        # Módulo/função origem
    error_code: str | None
    message: str
    # Campos obrigatórios para rastreio de consistência (ver Cláusula 26)
    fallback_activated: bool | None
    data_consistency_risk: Literal["NONE", "LOW", "HIGH"] | None
```

### 2. Verificação de Execução Obrigatória

Toda modificação de código requer, além da execução dos testes unitários:

1. **Execução completa** do aplicativo (backend e frontend, se aplicável)
2. **Verificação de Happy Path:** Executar pelo menos um fluxo principal completo com sucesso
3. **Verificação de logs** e arquivos de estado para garantir ausência de erros silenciosos
4. **Leitura das últimas 50 linhas** de `logs/last_run.log` (quando disponível) antes de declarar tarefa concluída
5. **Para serviços contínuos** (daemons, bots): presença de pelo menos **3 heartbeats consecutivos** no log sem erros intermediários

**Critério de suficiência:** O monitoramento é validado por **artefatos**, não por tempo arbitrário. A evidência é o log gerado com timestamp recente (< 5 minutos) demonstrando execução bem-sucedida.

**Ao finalizar qualquer tarefa de codificação**, incluir seção:

```markdown
## ✅ Checklist de Verificação

- [ ] Ciclo TDD respeitado para lógica de domínio/ports (§3)
- [ ] Testes unitários passaram
- [ ] Executou o código (backend e frontend)
- [ ] Happy path executado com sucesso (evidência em logs)
- [ ] Verificou logs e arquivos de estado para garantir que não há erros silenciosos
- [ ] Confirmou **ausência** de `FALLBACK_ACTIVATED` ou `data_consistency_risk: HIGH` nos logs
- [ ] Scripts de execução testados (se modificados)
```

> **Nota:** O checklist deve ser verificável por artefatos sempre que possível (logs gerados, outputs esperados), não apenas declarativo.

### 3. Test-Driven Development (TDD) Obrigatório

O ciclo **Red-Green-Refactor** é o processo padrão de desenvolvimento. Testes são a **especificação executável** — código de produção só existe para fazer testes passarem.

1. **Red:** Escrever um teste que falha, baseado no contrato ou requisito
2. **Green:** Implementar o **mínimo de código** necessário para o teste passar
3. **Refactor:** Melhorar a estrutura do código sem alterar comportamento (testes continuam verdes)

#### Escopo de Aplicação

| Tipo de código                                                           | TDD obrigatório?             | Justificativa                                                               |
| ------------------------------------------------------------------------ | ---------------------------- | --------------------------------------------------------------------------- |
| **Lógica de domínio** (funções puras, services, entities, value objects) | **Sim**                      | Contexto determinístico, alta testabilidade                                 |
| **Ports (Protocols)**                                                    | **Sim** (testes de contrato) | Define o comportamento esperado antes da implementação                      |
| **Adapters**                                                             | Recomendado                  | I/O dificulta TDD puro; testes de integração são aceitos após implementação |
| **Config/Composição**                                                    | Não                          | Código de cola, validado indiretamente                                      |
| **Scripts utilitários**                                                  | Não                          | Ferramentas de suporte, não lógica de negócio                               |

#### Regras do Ciclo

- **Proibido escrever código de produção sem teste falhando** para lógica de domínio e ports
- Cada ciclo Red-Green-Refactor deve ser **atômico**: não acumular múltiplos testes vermelhos antes de implementar
- O teste deve falhar **pelo motivo correto** (validar que o teste testa o que deveria testar)
- Na fase Green, implementar a solução **mais simples possível** — complexidade é adicionada apenas quando novos testes a exigirem (alinhamento natural com §21/YAGNI)
- Refactoring é feito **exclusivamente com testes verdes** — nunca refatorar com testes falhando
- **Baby steps:** preferir incrementos pequenos e verificáveis a grandes saltos de implementação

#### Integração com Fluxo de Geração (§20)

O passo 3 do fluxo de geração determinístico ("Criar testes baseados no contrato") é explicitamente um ciclo TDD:

1. Escrever testes que definem o comportamento esperado do contrato (Red)
2. Implementar a lógica de domínio incrementalmente (Green — passo 4 do fluxo)
3. Refatorar mantendo testes verdes (Refactor)
4. Repetir até que todos os requisitos do contrato estejam cobertos

#### Exceções Documentadas

TDD pode ser relaxado nas seguintes situações, **desde que documentado com justificativa**:

- **Código exploratório** em `sandbox/` (§15) — por definição descartável
- **Adapters de I/O puro** (ex: wrapper mínimo de SDK) — testar via integração após implementação
- **Bug fixes emergenciais** — permitido escrever o fix primeiro, mas o teste correspondente deve ser adicionado **antes do merge/commit**
- **Prototipagem de UI** — quando o feedback visual é o "teste"

> **Regra:** Se o código está em `src/domain/` ou `src/ports/`, TDD é **inegociável**. O teste é a especificação executável — código sem teste falhando anterior não é implementação, é rascunho.

### 4. Integridade de Testes

O processo de criação de testes segue o ciclo TDD obrigatório (§3). Além da metodologia, as seguintes regras de integridade se aplicam:

- Sucesso é **binário** (se um teste falha, a tarefa falha)
- Testes validam **comportamento e lógica de negócio**, não parâmetros hardcoded
- Refatorações preservam testes enquanto a lógica permanecer a mesma
- Funções puras do domínio têm **cobertura obrigatória** — mínimo **80%** de cobertura de linha para `src/domain/`
- Adapters e infraestrutura: cobertura **recomendada** mas não bloqueante
- Testes seguem padrão **Given-When-Then** para clareza semântica
- **Testes como âncora de contexto:** Ao gerar código, a IA deve priorizar leitura e alinhamento com testes existentes antes de criar novas implementações
- **Enforcement:** `pytest --cov=src/domain --cov-fail-under=80` deve ser usado no CI/check_all

---

## II. Arquitetura e Estrutura

### 5. Arquitetura Hexagonal Obrigatória

O sistema adota **Ports & Adapters** como padrão arquitetural inegociável:

- O **domínio** (regras de negócio puras) não possui dependências externas
- **Ports** definem contratos abstratos via `Protocol` (Python) ou interfaces equivalentes
- **Adapters** implementam os Ports e são substituíveis sem afetar o domínio
- Nenhum código de domínio importa diretamente implementações concretas de I/O, persistência ou serviços externos

### 6. Estrutura de Diretórios Canônica

A estrutura de pastas segue convenção **rígida e previsível**. Novos módulos seguem o padrão existente. A IA não decide estrutura, **segue convenção**.

#### Estrutura Completa (≥ 30 arquivos em `src/`)

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

#### Estrutura Mínima (< 30 arquivos em `src/`)

Para projetos menores, a estrutura plana é aceitável contanto que mantenha a separação lógica:

```
src/
├── domain/       # Regras de negócio + value objects (pode ser plano)
├── ports/        # Todos os Protocols (sem subdivisão inbound/outbound)
├── adapters/     # Todas as implementações (podem agrupar por feature)
├── config/       # Composição
└── shared/       # Utilitários
```

A subdivisão `inbound/outbound` de `ports/` e `adapters/` é obrigatória a partir de **5+ ports** OU **5+ adapters**.

#### Regras de importação (validadas por `scripts/check_imports.py`)

- `domain/` → não importa nada externo
- `ports/` → importa apenas `domain/`
- `adapters/` → importa `ports/` e `domain/`
- `config/` → importa tudo (ponto de composição)
- `shared/` → não importa `domain/`, `ports/`, `adapters/`, `config/`
- **Importação circular é proibida.** Se A precisa de B e B precisa de A, extraia a interface para um Port ou mova a lógica comum para Domain.

**Enforcement:** O script `scripts/check_imports.py` (portável, stdlib pura) valida estas regras via análise AST em cada execução de `check_all`. Se a estrutura hexagonal (`domain/`, `ports/`, etc.) ainda não existe no projeto, o script faz graceful skip.

### 7. Protocol-First Design

Toda dependência que **cruza a fronteira de I/O** (LLM, STT, TTS, storage, APIs, banco de dados) possui um **Protocol definido ANTES** de qualquer implementação:

- O Protocol é o **contrato**; implementações são detalhes
- Novos adapters são adicionados **sem modificar código existente**
- O Agente Executor **não cria implementações sem Protocol prévio**
- Protocols são **minimalistas**: métodos pequenos, sem defaults, sem comportamento implícito

> **Escopo de aplicação:** Esta cláusula aplica-se exclusivamente a dependências externas de I/O. Para lógica interna de domínio, ver §21 (YAGNI). A reconciliação entre §7 e §21 é definida pela **Regra da Fronteira de I/O** (ver §21).

```python
# ✅ Correto: métodos atômicos
class OrderRepository(Protocol):
    def create(self, order: Order) -> None: ...
    def update(self, order: Order) -> None: ...

# ❌ Incorreto: semântica oculta
class OrderRepository(Protocol):
    def save(self, order: Order, upsert: bool = True) -> None: ...
```

### 8. Functional Core, Imperative Shell

- Lógica de domínio é implementada como **funções puras** sempre que possível (mesma entrada produz mesma saída, sem side effects)
- I/O e side effects são **isolados na camada de adapters** (shell imperativo)
- Funções puras são a **unidade primária de teste**
- **Complexidade ciclomática máxima: 7.** Condicionais aninhadas profundas devem ser extraídas em funções nomeadas (buscar < 5; acima de 10 requer revisão obrigatória)

#### Exceção: Pipelines de Result

Funções que são **pipelines lineares de Results** (sem branches condicionais além do pattern matching do Result) têm limite elevado para **CC ≤ 12**, desde que:
- Cada branch seja exclusivamente check de `Success`/`Failure`
- Não haja lógica condicional aninhada dentro dos branches
- A função seja um pipeline linear (sem loops)

**Preferência:** Adotar métodos de encadeamento (`.map()`, `.bind()`, `.and_then()`) para reduzir branches explícitos e manter CC baixa:

```python
# ✅ Preferido: pipeline encadeado (CC = 1)
def process_order(cart: Cart, user: User) -> Result[Order, OrderError]:
    return (
        validate_cart(cart)
        .and_then(calculate_pricing)
        .and_then(check_inventory)
        .and_then(lambda stock: create_order(stock, user))
    )

# ⚠️ Aceitável: checks explícitos em pipeline linear (CC ≤ 12)
def process_order(cart: Cart, user: User) -> Result[Order, OrderError]:
    validated = validate_cart(cart)
    if isinstance(validated, Failure):
        return validated
    priced = calculate_pricing(validated.value)
    if isinstance(priced, Failure):
        return priced
    return create_order(priced.value, user)
```

### 9. Granularidade de Arquivos

Cada arquivo `.py` exporta no máximo **uma classe pública** ou um conjunto coeso de funções relacionadas:

- Arquivos com mais de **200 linhas** são candidatos a split (150-250 é aceitável se coeso)
- Arquivos com mais de **300 linhas** são **violações** que bloqueiam `check_all`
- A IA opera melhor com **unidades atômicas**
- Um arquivo, uma responsabilidade exportável
- **Critério de coesão:** se os testes sempre importam o mesmo conjunto de funções juntas, o arquivo está coeso
- **Exceções:** `__init__.py` e `conftest.py` são excluídos da contagem

**Enforcement:** O script `scripts/check_file_sizes.py` (portável, stdlib pura) emite:
- `WARN` para arquivos >200 linhas (não-blank)
- `ERROR` para arquivos >300 linhas (bloqueia `check_all`)

Limites são configuráveis via `--warn` e `--error`.

```
❌ Ruim: services/user_service.py (500+ linhas)
✅ Bom:  services/user/create_user.py (~50-100 linhas)
         services/user/authenticate_user.py
```

---

## III. Tipos, Dados e Validação

### 10. Imutabilidade por Padrão

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

### 11. Erros como Tipos de Domínio (Result Pattern)

Erros de negócio são **Value Objects tipados** que implementam o Protocol `DomainError` (§25), nunca exceções genéricas.

> **Implementação de referência:** `scripts/shared/result.py` contém a implementação portável e canônica de `Success[T]`, `Failure[E]`, `Result`, `DomainError` Protocol, `collect_results()` e `try_result()`. Ao iniciar um novo projeto, copie `scripts/shared/result.py` para `src/shared/result.py`. **Não reimplemente** — use a versão fornecida.

```python
@dataclass(frozen=True)
class Success(Generic[T]):
    value: T

@dataclass(frozen=True)
class Failure(Generic[E]):
    error: E

Result = Union[Success[T], Failure[E]]
```

`Success` e `Failure` expõem métodos de encadeamento (`.map()`, `.and_then()`, `.map_error()`, `.unwrap()`, `.unwrap_or()`) que permitem pipelines lineares com CC = 1 (ver §8).

Todo tipo `E` usado em `Result[T, E]` **deve** satisfazer o Protocol `DomainError` (§25), garantindo que erros sejam logáveis e mapeáveis automaticamente:

```python
@dataclass(frozen=True)
class OrderCreationError:
    """Satisfaz DomainError Protocol."""
    code: str
    message: str

    @classmethod
    def empty_cart(cls) -> "OrderCreationError":
        return cls(code="ORDER_EMPTY_CART", message="Cannot create order from empty cart")

# Uso
def create_order(cart: Cart) -> Result[Order, OrderCreationError]:
    if not cart.items:
        return Failure(OrderCreationError.empty_cart())
    return Success(Order(...))
```

O sistema de tipos **obriga** a tratar o erro. Fluxo previsível, sem surpresas.

> **Hierarquia:** §11 define o padrão de fluxo (Result). §25 define o contrato semântico dos erros (DomainError). Todo `E` em `Failure[E]` satisfaz `DomainError`. Não há ambiguidade.

### 12. Validação Semântica e Normalização Tipada

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

### 13. Configuração Externa e Zero Hardcoding

É **terminantemente proibido** o uso de valores literais ou parâmetros hardcoded no código:

- URLs, credenciais, portas, timeouts, limites → arquivos de configuração (`.env`)
- O Agente Executor extrai todo parâmetro configurável para o ambiente
- **`.env` e `.env.example` devem estar sempre sincronizados**: toda variável em `.env` deve existir em `.env.example` (com valor de exemplo) e vice-versa
- Violações desta regra **invalidam a entrega**

#### Validação de Configuração em Startup

O ponto de entrada do aplicativo **deve** validar configuração antes de qualquer operação:

1. Usar `pydantic.BaseSettings` (ou equivalente) com tipos explícitos
2. Toda variável tem tipo, default (se opcional) e descrição
3. Startup falha **imediatamente** se variável obrigatória está ausente
4. Script `scripts/validate_env.py` (portável, fornecido em `scripts/`) gera `.env.example` a partir da classe Settings (**single source of truth**) e valida que `.env` contém todas as variáveis obrigatórias

```bash
# Gera .env.example e valida .env
python scripts/validate_env.py

# Apontar para outro arquivo de config
python scripts/validate_env.py --config-file src/lib/config.py
```

O script usa análise AST (zero dependencies externas) para extrair campos de `BaseSettings`, incluindo `env_prefix` e defaults.

> **Regra:** Sincronização manual entre `.env` e `.env.example` é substituída por geração automatizada. A classe `Settings` é a fonte canônica.

### 14. Injeção de Dependências Explícita

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

### 15. Contratos Antes de Comportamento

O Agente Executor recebe **contratos** (Protocols, interfaces, tipos) como entrada primária:

- Prompts que descrevem comportamento sem contrato prévio são rejeitados ou convertidos para contract-first
- A IA **implementa contratos**, não inventa interfaces
- Código gerado sem contrato prévio é tratado como **rascunho**, não como entrega

**Exceção - Fase de Descoberta:** Para exploração de APIs externas novas, é permitido criar código "sujo" em `sandbox/` ou `explorations/`, marcado como descartável e **nunca integrado ao `src/`**. Este código serve apenas como especificação informal para criar o Protocol real.

**Governança de Código Exploratório:**
1. `sandbox/` é listado no `.gitignore` por padrão
2. Código exploratório tem **prazo máximo de 5 dias úteis**, rastreado via comentário `# @exploration-deadline YYYY-MM-DD` (opcionalmente com `reason: descrição`) na primeira linha
3. Script `scripts/check_explorations.py` (portável, fornecido em `scripts/`) falha se existem arquivos expirados em `sandbox/`
4. **Promoção para `src/`** exige: Protocol criado, testes escritos, tutorial de extensibilidade (§17)
5. Código exploratório que exceda o prazo sem promoção deve ser **deletado ou formalmente renovado** com justificativa

```python
# sandbox/test_new_api.py
# @exploration-deadline 2025-03-15 reason: testando integração com API v3
import requests
...
```

### 16. Glossário de Linguagem Ubíqua

Um conceito possui **um único nome canônico** em todo o sistema:

- Não misturar `User`, `Customer`, `Account` para o mesmo conceito
- Não misturar `Repository`, `Gateway`, `Storage` arbitrariamente
- Manter arquivo `docs/glossary.md` com definições fechadas
- Para projetos com mais de 10 entidades de domínio, **adicionalmente** manter glossário como código em `src/shared/glossary.py` com constantes/Enums documentados que espelhem `docs/glossary.md`

### 17. Tutorial de Extensibilidade Obrigatório

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

### 18. Scripts de Execução Obrigatórios

Todo projeto mantém uma pasta `scripts/` com scripts de execução para operações essenciais. O objetivo é **não obrigar o usuário a consultar README.md ou memorizar comandos**.

#### Estratégia Dual: Cross-Platform com Conveniência Nativa

- **Primário:** Entry points Python via `pyproject.toml` ou módulo `scripts/` (cross-platform por natureza)
- **Conveniência Windows:** Scripts `.bat` que chamam os entry points Python
- **Conveniência Unix/CI:** Scripts `.sh` equivalentes (ou `Makefile`)

**Critério mínimo:** O usuário deve conseguir executar qualquer operação essencial com **um único comando**, independente do SO.

```
scripts/
├── check_all.py               # Orquestrador: mypy → pytest → todos os checks (ver §1)
├── check_all.bat / check_all.sh  # Wrappers nativos para check_all.py
├── check_imports.py           # Valida regras de importação hexagonal (ver §6)
├── check_file_sizes.py        # Valida limite de linhas por arquivo (ver §9)
├── generate_map.py            # Gera docs/map.md a partir de docstrings (ver §24)
├── validate_env.py            # Gera .env.example e valida .env (ver §13)
├── check_explorations.py      # Verifica prazos em sandbox/ (ver §15)
├── shared/
│   └── result.py              # Result[T,E], Success, Failure, DomainError (ver §11/§25)
├── run.bat / run.sh           # Executa o aplicativo principal
├── run_dev.bat / run_dev.sh   # Executa em modo desenvolvimento
├── run_tests.bat / run_tests.sh   # Executa todos os testes
├── install.bat / install.sh   # Instala dependências
└── [feature]_*.bat/.sh        # Variações por funcionalidade
```

> **Kit Portável:** Os scripts `check_all.py`, `check_imports.py`, `check_file_sizes.py`, `generate_map.py`, `validate_env.py`, `check_explorations.py` e `shared/result.py` são **portáveis entre projetos**. São zero-dependency (stdlib pura) e acompanham as cláusulas pétreas como enforcement automatizado. Ao iniciar um novo projeto, copie a pasta `scripts/` inteira junto com este documento.

**Regras:**
- Scripts são a **porta de entrada** ao software desenvolvido
- Qualquer adição de funcionalidade que couber novos scripts com variações de inicialização deve criá-los
- Mudanças estruturais que precisem ajustar os scripts atuais **devem atualizá-los**
- **Todos os scripts devem ser testados** após qualquer modificação
- Scripts devem ser **autoexplicativos** (incluir `echo`/`print` descrevendo o que fazem)
- **Encoding UTF-8 e line endings consistentes** (LF para `.sh`; CRLF para `.bat`)

**Documentação mínima de cada script:**
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

### 19. Reconhecimento de Limitações do Agente Executor

O Agente Executor (IA) reconhece que:

- **Não mantém modelo mental persistente** do sistema
- **Não tem consciência do custo de manutenção futura**
- **Tende a otimizar localmente**

Portanto:

- **Decisões arquiteturais são humanas** (IA não sugere estrutura, segue convenção)
- **Validação é por ferramentas** (IA não revisa próprio código)
- **Prompts devem ser determinísticos** com contratos explícitos (IA não debate, executa)

### 20. Fluxo de Geração Determinístico

Ao implementar funcionalidades, seguir ordem estrita. O fluxo é **proporcional ao tipo de mudança**:

#### Classificação de Mudanças

| Tipo           | Critério                                                  | Passos Obrigatórios        |
| -------------- | --------------------------------------------------------- | -------------------------- |
| **Trivial**    | Config, typos, constantes, ajustes de `.env`              | 6 + 10                     |
| **Menor**      | Lógica em ≤ 2 arquivos, sem mudança de contrato           | 3–6 + 10                   |
| **Maior**      | Novo feature, novo adapter, novo Port                     | Todos (0–10)               |
| **Estrutural** | Mudança de Protocol, migração, refatoração de arquitetura | Todos + Impact Graph (§27) |

#### Fluxo Completo (para mudanças Maiores e Estruturais)

0. **Planejamento:** Emitir plano de execução listando arquivos a criar/modificar e como respeitam as cláusulas pétreas
0.5. **Análise de Impacto (Impact Graph):** Antes de qualquer código, listar TODOS os arquivos que importam os módulos afetados e classificar impacto: `[QUEBRA CONTRATO]` ou `[INTERNO]` (ver Cláusula 27)
1. Verificar **glossário** para garantir consistência de termos
2. Identificar/criar **Protocol** (Port) necessário (respeitando Regra da Fronteira de I/O, §21)
3. Criar **testes** baseados no contrato seguindo ciclo TDD (§3): testes falhando primeiro (Red), implementação mínima (Green, passo 4), refatoração com testes verdes (Refactor)
4. Implementar **lógica de domínio** (funções puras) — fase Green do TDD
5. Implementar **Adapter** se necessário
6. Validar com **mypy** e **pytest**
7. Atualizar **container.py** se nova dependência
8. Criar/atualizar **tutorial de extensibilidade**
9. Atualizar **scripts de execução** se aplicável
10. **Executar e monitorar** aplicação completa (ver §2)

> **Regra de proporcionalidade:** Para mudanças Triviais, executar apenas validação (passo 6) e monitoramento (passo 10). Para mudanças Menores, começar nos testes (passo 3). A classificação errada para baixo (tratar Maior como Menor) é uma violação; para cima (tratar Trivial como Maior) é apenas ineficiência.

### 21. YAGNI Rigoroso (Proibição de Abstrações Prematuras)

- **Não criar** interfaces/Protocols "apenas porque pode precisar no futuro"
- **Proibido** criar "base classes", "abstract services" ou "helpers genéricos" sem uso concreto atual
- A IA tende a over-engineer; esta cláusula força simplicidade
- **Alinhamento com TDD (§3):** A fase Green do ciclo TDD reforça YAGNI naturalmente — implementar apenas o mínimo necessário para o teste passar

#### Regra da Fronteira de I/O (Reconciliação §5/§7 vs §21)

O conflito entre "Protocol para tudo" (§5/§7) e "só na segunda implementação" é resolvido por um critério determinístico:

| Tipo de componente                                                       | Quando criar Protocol                        | Cláusula prevalente |
| ------------------------------------------------------------------------ | -------------------------------------------- | ------------------- |
| **Dependência externa de I/O** (LLM, storage, API, DB, serviços de rede) | Desde a **primeira** implementação           | §5/§7 prevalece     |
| **Lógica interna de domínio** (cálculos, transformações, validações)     | Apenas na **segunda** implementação concreta | §21 prevalece       |

**Critério decisivo:** Se o componente **faz I/O ou depende de infraestrutura externa**, Protocol é obrigatório desde o início (o custo de desacoplar uma dependência externa rígida depois é maior que o custo da abstração). Se é **lógica pura**, comece com função concreta e extraia Protocol só quando surgir variação real de comportamento.

> **Teste mental:** "Se eu precisar trocar este componente por uma implementação fake em testes, eu precisaria de mock/patch?" Se sim → Protocol obrigatório. Se basta chamar a função com argumentos diferentes → YAGNI prevalece.

### 22. Convenções Determinísticas de Nomenclatura

Para eliminar ambiguidade e facilitar navegação:

- **Ports:** `[Entity][Action]Port` (ex: `UserRepositoryPort`, `EmailSenderPort`)
- **Adapters:** `[Tech][Entity]Adapter` (ex: `PostgresUserAdapter`, `SendGridEmailAdapter`)
- **Services de domínio:** `[action]_[entity].py` (ex: `create_user.py`, `validate_order.py`)
- **Use Cases:** `[Verbo][Entidade]UseCase` com método único `execute()` (ex: `CreateOrderUseCase`)
- **Value Objects:** substantivos adjetivados (ex: `EmailAddress`, `PositiveInteger`)
- **Erros:** `[Domain][ErrorType]Error` (ex: `UserNotFoundError`, `PaymentFailedError`)
- **`__init__.py`:** Apenas re-exportações públicas — proibido lógica, proibido import circular
- **Configuração:** `config.py` na raiz do pacote ou em `src/config/` — nunca espalhada em múltiplos módulos
- **Testes:** `test_[módulo].py` espelhando a estrutura de `src/` (ex: `tests/unit/test_create_user.py` testa `src/domain/services/create_user.py`)
- **Fixtures:** em `conftest.py` do diretório de testes relevante — nunca em arquivos de teste individuais

### 23. Proibição de Magia e Metaprogramação

LLMs quebram completamente com lógica implícita invisível. É **terminantemente proibido**:

- Metaprogramação (metaclasses, `__new__` com lógica complexa)
- Decorators com lógica implícita de transformação (decorators simples de logging são permitidos)
- Magic methods fora de Value Objects e dataclasses
- Reflection para alterar comportamento em runtime
- Monkey patching
- Import-time side effects

**Regra:** Se o comportamento não é óbvio lendo o código linha a linha, está proibido.

### 24. Mapa de Contexto do Projeto (Automatizado)

Para projetos com mais de 20 arquivos, manter um **mapa de navegação** atualizado em `docs/map.md`:

- O mapa serve como "GPS" para a IA em cada novo prompt
- O mapa é **gerado automaticamente** por `scripts/generate_map.py` (portável, fornecido em `scripts/`), **nunca mantido manualmente**

#### Mecanismo de Geração

1. Script `scripts/generate_map.py` percorre `src/` e gera `docs/map.md` a partir da **docstring de módulo** (primeira linha de cada `.py`)
2. Para cada arquivo, exibe: caminho, contagem de linhas e primeira linha da docstring
3. Arquivos sem docstring são marcados com ⚠️ no mapa gerado
4. O script é executado automaticamente como parte de `scripts/check_all.py`
5. Hook de pre-commit pode regenerar o mapa opcionalmente

```bash
# Gerar mapa
python scripts/generate_map.py

# Apontar para outro diretório ou output
python scripts/generate_map.py --src-dir src --output docs/map.md
```

> **Princípio:** "Ferramentas são a lei" (§1). Manutenção manual de mapa contradiz este princípio e é portanto proibida.

**Formato gerado:**
```markdown
# Mapa de Módulos
> Gerado automaticamente em YYYY-MM-DD HH:MM UTC por scripts/generate_map.py

## domain/
| Módulo                    | Linhas | Descrição                               |
| ------------------------- | ------ | --------------------------------------- |
| `entities/user.py`        | 85     | Entidade User com validações de domínio |
| `services/create_user.py` | 42     | Lógica pura de criação de usuário       |
```

### 25. Erros com Semântica Formal (Contrato Unificado)

Todo erro de domínio segue um **contrato semântico único**, unificado com o Result Pattern (§11):

```python
@runtime_checkable
class DomainError(Protocol):
    @property
    def code(self) -> str: ...
    @property
    def message(self) -> str: ...
    @property
    def context(self) -> dict[str, Any]:
        """Contexto estruturado opcional para logging/telemetria."""
        return {}
```

> **Implementação de referência:** A definição canônica do Protocol `DomainError` está em `scripts/shared/result.py`, junto com `Success`, `Failure` e `Result`. Use `@runtime_checkable` para permitir verificação com `isinstance()` em adapters de apresentação.

**Hierarquia definitiva:**
- §11 define o **padrão de fluxo** (`Result[T, E]` com `Success`/`Failure`)
- §25 define o **contrato semântico** que todo `E` em `Failure[E]` deve satisfazer
- Todo tipo usado como `E` em `Result[T, E]` **deve** implementar `DomainError`
- Enums sem `code`/`message` são **proibidos** como tipo de erro em Results

Isso permite:
- Logs automáticos padronizados (todo erro tem `code` e `message` acessíveis)
- Mapeamento determinístico para HTTP status codes ou respostas CLI
- Menos if/else em adapters de apresentação
- **Zero ambiguidade** na implementação de erros
- `context` para telemetria estruturada sem poluir `message`

---

## VIII. Integridade em Transições e Migrações

### 26. Integridade Radical em Transições (Fail-Fast Auditável)

Durante refatorações estruturais ou migrações (ex: troca de banco, mudança de API), a integridade dos dados tem **prioridade absoluta** sobre a disponibilidade.

- **Modo Estrito:** O sistema deve suportar uma flag `STRICT_ARCHITECTURE_MODE=true` (via `.env`). Quando ativa:
  - Falhas em sistemas secundários (ex: dual-write) disparam `ArchitectureViolationError`, nunca warnings
  - Discrepâncias de contrato interrompem a execução
- **Proibição de Degradação Silenciosa:** É proibido capturar exceções críticas e logar apenas como `WARNING` sem interromper o fluxo, a menos que explicitamente documentado como estratégia de resiliência em produção estável

#### Protocolo de Crash Controlado

O `STRICT_ARCHITECTURE_MODE` não significa "crash e morra". Significa **crash controlado** com auditoria:

1. **Antes do crash:** Persistir estado da operação em andamento em `logs/fatal_violation.json` com contexto completo (Impact Graph da operação, dados parciais, timestamp)
2. **Notificação:** Emitir log `ERROR` + mecanismo de notificação configurado em `.env` (`ALERT_WEBHOOK_URL`)
3. **Idempotência:** Toda operação de escrita deve ser idempotente, permitindo replay seguro após crash
4. **Rollback em dual-write:** Se a falha ocorrer durante um dual-write ou migração, o sistema deve reverter a operação no sistema primário antes de encerrar
5. **Circuit Breaker:** Após N falhas consecutivas em sistema secundário (configurável via `STRICT_MODE_MAX_FAILURES` em `.env`), o sistema entra em modo "manutenção" (rejeita novas operações) em vez de crashar repetidamente

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
        "crash_state_file": "logs/fatal_violation.json",  # Obrigatório
    },
)
```

> **Regra:** `try...except...warning` em operações de escrita é **terminantemente proibido** quando `STRICT_ARCHITECTURE_MODE=true`.

### 27. Rastreabilidade de Dependências (Impact Graph)

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

### 28. Definition of Done para Migrações

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
| TDD obrigatório                 | Código nasce testado e mínimo    |
| Arquivos pequenos (<200 linhas) | IA lê contexto completo          |
| Estrutura previsível            | IA navega sem "descobrir"        |
| Protocols como spec             | IA sabe o que implementar        |
| Result pattern                  | Fluxos explícitos, sem surpresas |
| Testes como âncora              | IA aprende por exemplo           |
| Composition Root                | Ponto único de mudança           |
| Imutabilidade                   | Menos estados para rastrear      |
| Scripts cross-platform          | Execução sem fricção             |
| Verificação pós-código          | Bugs detectados em runtime       |
| YAGNI rigoroso                  | Evita over-engineering           |
| Nomenclatura determinística     | Zero ambiguidade                 |
| Logs estruturados               | Auditoria automática             |
| Proibição de magia              | Comportamento sempre explícito   |
| Mapa de contexto                | IA navega sem "descobrir"        |
| .env sincronizado               | Configuração sempre completa     |
| Fail-Fast Auditável             | Falhas nunca são silenciosas     |
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

## Kit Portável de Enforcement

As cláusulas pétreas acompanham um **kit de scripts portáveis** que implementam o enforcement automatizado prescrito. Ao iniciar um novo projeto, copie:

1. **Este arquivo** (`prompts/unalterable_clauses.md`) como referência arquitetural
2. **A pasta `scripts/`** com todos os scripts de enforcement

```
scripts/
├── check_all.py              # Orquestrador (§1) — mypy → pytest → todos os checks
├── check_all.bat             # Wrapper Windows
├── check_all.sh              # Wrapper Unix
├── check_imports.py          # Validação de fronteiras hexagonais (§6)
├── check_file_sizes.py       # Validação de limite de linhas (§9)
├── generate_map.py           # Geração de docs/map.md (§24)
├── validate_env.py           # Geração de .env.example e validação (§13)
├── check_explorations.py     # Governança de sandbox/ (§15)
└── shared/
    └── result.py             # Result[T,E], DomainError Protocol (§11/§25)
```

**Características do kit:**
- **Zero dependencies externas** — todos usam apenas stdlib Python (exceto `validate_env.py` que requer `pydantic-settings` no projeto alvo)
- **Graceful skip** — scripts que dependem de estrutura hexagonal (`domain/`, `ports/`) fazem skip silencioso se a estrutura não existe ainda
- **Cross-platform** — Python puro, funciona em Windows, Linux e macOS
- **Configuráveis** — todos aceitam `--src-dir` e parâmetros relevantes via CLI
- `shared/result.py` deve ser copiado para `src/shared/result.py` no projeto alvo como implementação canônica do Result Pattern

> **Regra:** Os scripts são a materialização das cláusulas. Sem eles, as cláusulas são apenas texto — com eles, são **enforcement real**.

---

**Arquitetura boa para IA é: previsível 📐 · repetitiva 🔁 · restritiva 🔒 · semanticamente explícita 🧠 · verificável por artefatos ✅**