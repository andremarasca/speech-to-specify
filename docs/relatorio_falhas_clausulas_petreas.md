# Relatório de Falhas Estruturais e Arquiteturais — Cláusulas Pétreas

> **Data:** 2026-02-07  
> **Escopo:** Análise crítica do documento `prompts/unalterable_clauses.md` com foco em contradições internas, prescrições impraticáveis, lacunas lógicas e desalinhamento com a realidade do projeto.  
> **Status:** ✅ **TODAS AS 14 FALHAS CORRIGIDAS** em `prompts/unalterable_clauses.md`

---

## Sumário Executivo

As Cláusulas Pétreas constituem um documento robusto de governança arquitetural para projetos assistidos por IA. A análise identificou **14 falhas** distribuídas em 4 categorias: contradições internas entre cláusulas, prescrições irrealistas ou impraticáveis, lacunas lógicas que geram ambiguidade, e desalinhamento entre as regras prescritas e a estrutura real do projeto.

**Todas as falhas foram corrigidas** diretamente no arquivo `prompts/unalterable_clauses.md`. As correções preservam o espírito original das cláusulas enquanto eliminam contradições e adicionam mecanismos de enforcement automatizado.

---

## Índice de Falhas

| #   | Cláusula   | Categoria    | Severidade | Título                                                                  | Status      |
| --- | ---------- | ------------ | ---------- | ----------------------------------------------------------------------- | ----------- |
| F01 | §4 vs §20  | Contradição  | 🔴 Alta     | Hexagonal obrigatório vs YAGNI rigoroso                                 | ✅ Corrigido |
| F02 | §6 vs §20  | Contradição  | 🔴 Alta     | Protocol-First vs "só na segunda implementação"                         | ✅ Corrigido |
| F03 | §5         | Impraticável | 🟡 Média    | Estrutura canônica pressupõe escala que nem todo projeto atinge         | ✅ Corrigido |
| F04 | §2         | Lacuna       | 🟡 Média    | Monitoramento de 1 minuto é arbitrário e não verificável                | ✅ Corrigido |
| F05 | §17        | Lacuna       | 🟡 Média    | Scripts .bat excluem outros SO e não mencionam cross-platform           | ✅ Corrigido |
| F06 | §7         | Contradição  | 🟡 Média    | Complexidade ciclomática máxima 7 conflita com Result Pattern           | ✅ Corrigido |
| F07 | §8 vs §5   | Contradição  | 🟠 Média    | Granularidade de 200 linhas + estrutura canônica = explosão de arquivos | ✅ Corrigido |
| F08 | §19        | Lacuna       | 🟡 Média    | Fluxo de 11 passos sem critério de priorização ou bypass documentado    | ✅ Corrigido |
| F09 | §25        | Impraticável | 🔴 Alta     | STRICT_MODE crash em produção sem estratégia de rollback                | ✅ Corrigido |
| F10 | §1         | Lacuna       | 🟡 Média    | mypy --strict obrigatório mas sem enforcement automatizado no CI        | ✅ Corrigido |
| F11 | §10 vs §24 | Redundância  | 🟢 Baixa    | Dois padrões de erro sobrepostos sem hierarquia clara                   | ✅ Corrigido |
| F12 | §12        | Lacuna       | 🟡 Média    | .env sincronizado mas sem mecanismo de validação em startup             | ✅ Corrigido |
| F13 | §23        | Impraticável | 🟡 Média    | Mapa de contexto manualmente atualizado é insustentável                 | ✅ Corrigido |
| F14 | §14        | Contradição  | 🟡 Média    | Exceção de "Fase de Descoberta" cria zona cinzenta permanente           | ✅ Corrigido |

---

## Análise Detalhada

### F01 — Hexagonal Obrigatório vs YAGNI Rigoroso

**Cláusulas afetadas:** §4 (Arquitetura Hexagonal Obrigatória) vs §20 (YAGNI Rigoroso)

**O problema:**  
A §4 exige Ports & Adapters como padrão **inegociável**, incluindo separação completa em `domain/`, `ports/inbound/`, `ports/outbound/`, `adapters/inbound/`, `adapters/outbound/`. No entanto, a §20 declara:

> *"Protocol só é criado quando existe ou está sendo implementado imediatamente um adapter"*  
> *"Quando em dúvida: implemente primeiro como função concreta, extraia Protocol só na segunda implementação"*

Essas duas regras são **mutuamente exclusivas**. Se a arquitetura hexagonal é obrigatória desde o início, cada dependência externa precisa de um Protocol antes da primeira implementação. Mas o YAGNI diz para não criar abstrações até a segunda implementação.

**Por que falha:**  
Na prática, o desenvolvedor (ou IA) não sabe qual regra seguir. Se há apenas um adapter de LLM (ex: OpenAI), a §20 diz "não crie Protocol ainda". Mas a §4 diz "o domínio não pode importar implementações concretas de I/O". Resultado: paralisia decisória ou violação inevitável de uma das duas cláusulas.

**Evidência no projeto:**  
O projeto atual usa `services/llm/base.py` como classe base — nem hexagonal puro (§4), nem YAGNI puro (§20). É um compromisso pragmático que **ambas as cláusulas proíbem**.

**Solução proposta:**  
Introduzir um **critério de limiar** que reconcilie ambas as cláusulas:

```markdown
### Regra de Reconciliação §4/§20 — Limiar de Abstração

- **Dependências externas de I/O** (LLM, storage, APIs, banco de dados): 
  Protocol é obrigatório desde a PRIMEIRA implementação (§4 prevalece)
- **Serviços internos de domínio** (cálculos, transformações, validações): 
  Protocol só na segunda implementação (§20 prevalece)
- **Critério decisivo:** Se o componente faz I/O ou depende de infraestrutura 
  externa, §4 prevalece. Se é lógica pura, §20 prevalece.
```

---

### F02 — Protocol-First vs "Só na Segunda Implementação"

**Cláusulas afetadas:** §6 (Protocol-First Design) vs §20 (YAGNI)

**O problema:**  
A §6 declara explicitamente:

> *"Toda dependência externa possui um Protocol definido ANTES de qualquer implementação"*

Enquanto a §20 prescreve:

> *"Quando em dúvida: implemente primeiro como função concreta, extraia Protocol só na segunda implementação"*

**Por que falha:**  
É uma contradição direta e binária. "Toda dependência" vs "só na segunda". Não há zona cinzenta — ou se cria o Protocol antes ou se espera. Ambas são apresentadas como inegociáveis.

**Solução proposta:**  
A §20 deve **excetuar explicitamente** dependências externas do escopo de YAGNI:

```markdown
### §20 — Escopo de Aplicação

YAGNI aplica-se a:
- Abstrações internas de domínio
- Hierarquias de classes de serviço
- Patterns genéricos sem segundo uso concreto

YAGNI NÃO se aplica a:
- Ports para dependências externas (coberto por §6)
- Contratos de I/O (coberto por §4)
- Schemas de dados em fronteiras de sistema
```

---

### F03 — Estrutura Canônica Pressupõe Escala

**Cláusula afetada:** §5 (Estrutura de Diretórios Canônica)

**O problema:**  
A estrutura prescrita tem 10+ diretórios (`domain/entities/`, `domain/value_objects/`, `domain/services/`, `domain/errors/`, `ports/inbound/`, `ports/outbound/`, `adapters/inbound/`, `adapters/outbound/`, `config/`, `shared/`). Para projetos de escopo pequeno/médio (como este, com ~40 arquivos em `src/`), isso cria uma profundidade de diretórios desproporcional com muitas pastas contendo 1-2 arquivos.

**Por que falha:**  
A própria §8 reconhece que "a IA opera melhor com unidades atômicas". Paradoxalmente, ter 10 diretórios com 1 arquivo cada **dificulta** a navegação da IA (mais níveis para percorrer) sem ganho real de separação de responsabilidades. Em projetos pequenos, a estrutura se torna burocracia sem substância.

**Evidência no projeto:**  
O projeto atual tem uma estrutura mais plana (`lib/`, `models/`, `services/`) que, apesar de não ser hexagonal, é mais navegável para o tamanho atual do codebase.

**Solução proposta:**  
Adicionar uma **cláusula de escala progressiva**:

```markdown
### §5.1 — Escala Progressiva da Estrutura

A estrutura canônica completa aplica-se a projetos com mais de 30 arquivos em src/.
Para projetos menores, a estrutura mínima aceitável é:

src/
├── domain/       # Regras de negócio + value objects (pode ser plano)
├── ports/        # Todos os Protocols (sem subdivisão inbound/outbound)
├── adapters/     # Todas as implementações (podem agrupar por feature)
├── config/       # Composição
└── shared/       # Utilitários

A subdivisão inbound/outbound de ports/ e adapters/ é obrigatória 
a partir de 5+ ports OU 5+ adapters.
```

---

### F04 — Monitoramento de 1 Minuto é Arbitrário

**Cláusula afetada:** §2 (Verificação de Execução Obrigatória)

**O problema:**  
A cláusula exige "monitoramento ativo por pelo menos 1 minuto". Esse número é:
1. **Arbitrário** — por que 1 minuto e não 30 segundos ou 5 minutos?
2. **Não verificável** — não há como provar que alguém (ou uma IA) "monitorou por 1 minuto"
3. **Insuficiente para processos lentos** — um processamento de LLM pode levar 3+ minutos
4. **Excessivo para scripts rápidos** — uma validação de schema termina em 2 segundos

**Por que falha:**  
Uma regra não verificável por artefatos contradiz o princípio fundamental do próprio documento: "verificabilidade automática sobre a elegância". O tempo fixo de 1 minuto não é verificável por nenhum artefato.

**Solução proposta:**

```markdown
### §2 — Critério de Monitoramento Baseado em Artefatos

Em vez de tempo fixo, o monitoramento é validado por:
1. **Execução completa** de pelo menos um fluxo principal (happy path)
2. **Ausência de erros** nos logs gerados durante a execução
3. **Arquivo de evidência:** presença do log da execução em `logs/last_run.log` 
   com timestamp recente (< 5 minutos)
4. **Para serviços contínuos (daemons, bots):** presença de pelo menos 
   3 heartbeats consecutivos no log sem erros intermediários
```

---

### F05 — Scripts .bat Excluem Outros Sistemas Operacionais

**Cláusula afetada:** §17 (Scripts de Execução .bat Obrigatórios)

**O problema:**  
A cláusula prescreve exclusivamente `.bat` (Windows). Isso:
1. Exclui desenvolvedores em Linux/macOS
2. Não menciona alternativas cross-platform (Makefile, task runners, scripts Python)
3. Contradiz práticas modernas de DevOps (containers, CI/CD com shell scripts)

**Por que falha:**  
Se o projeto precisar de CI/CD (GitHub Actions, GitLab CI), os `.bat` são inúteis — esses ambientes rodam Linux. A cláusula é excessivamente acoplada ao Windows como ambiente de desenvolvimento.

**Solução proposta:**

```markdown
### §17 — Scripts de Execução Obrigatórios

#### Estratégia dual:
- **Primário:** Scripts Python `cli/` com entry points no `pyproject.toml`
  (cross-platform por natureza)
- **Conveniência Windows:** Scripts `.bat` que chamam os entry points Python
- **Conveniência Unix:** Scripts `.sh` equivalentes (ou Makefile)

#### Critério mínimo:
O usuário deve conseguir executar qualquer operação essencial com 
UM ÚNICO COMANDO, independente do SO.
```

---

### F06 — Complexidade Ciclomática 7 Conflita com Result Pattern

**Cláusulas afetadas:** §7 (Complexidade ciclomática máxima: 7) vs §10 (Result Pattern)

**O problema:**  
O Result Pattern exige pattern matching ou verificação explícita de `Success`/`Failure` em cada chamada. Em funções que fazem 3-4 operações sequenciais com Result, cada uma adiciona um branch:

```python
def process_order(cart: Cart, user: User) -> Result[Order, OrderError]:
    validated = validate_cart(cart)          # branch 1-2 (Success/Failure)
    if isinstance(validated, Failure):
        return validated
    
    priced = calculate_pricing(validated.value)  # branch 3-4
    if isinstance(priced, Failure):
        return priced
    
    stocked = check_inventory(priced.value)      # branch 5-6
    if isinstance(stocked, Failure):
        return stocked
    
    return create_order(stocked.value, user)      # branch 7-8
```

4 operações com Result já excedem a complexidade ciclomática de 7.

**Por que falha:**  
A prescrição simultânea de Result Pattern + CC≤7 força funções de composição a serem tão granulares que a navegabilidade é prejudicada — o contrário do princípio fundamental do documento.

**Solução proposta:**

```markdown
### §7.1 — Exceção para Composição de Results

Funções que são pipelines lineares de Results (sem branches condicionais 
além do pattern matching do Result) têm limite elevado para CC ≤ 12, 
desde que:
- Cada branch seja exclusivamente Success/Failure check
- Não haja lógica condicional aninhada
- A função seja um pipeline linear (sem loops)

Alternativamente, adotar um operador `bind`/`and_then` para reduzir 
branches explícitos:

def process_order(cart: Cart, user: User) -> Result[Order, OrderError]:
    return (
        validate_cart(cart)
        .and_then(calculate_pricing)
        .and_then(check_inventory)
        .and_then(lambda stock: create_order(stock, user))
    )
```

---

### F07 — Granularidade de 200 Linhas + Estrutura Canônica = Explosão de Arquivos

**Cláusulas afetadas:** §8 (Granularidade de Arquivos) + §5 (Estrutura Canônica) + §23 (Mapa de Contexto)

**O problema:**  
Se cada arquivo tem ≤200 linhas, e a estrutura tem 10+ diretórios, um projeto de tamanho moderado (~5000 linhas de domínio) gera **25-50 arquivos** distribuídos em 10+ pastas. A §23 exige um mapa manual de cada um desses arquivos.

**Por que falha:**  
A combinação cria um **ciclo de manutenção insustentável**: cada novo arquivo exige atualização manual do mapa (§23), que por sua vez precisa ser mantido sincronizado manualmente — algo que a própria IA não faz de forma confiável (reconhecido na §18: "não mantém modelo mental persistente").

**Solução proposta:**

```markdown
### §23 — Mapa de Contexto Automatizado

O mapa de contexto deve ser GERADO por ferramenta, não mantido manualmente.

Estratégias aceitáveis:
1. Script em `scripts/generate_map.py` que percorre `src/` e gera `docs/map.md`
   a partir de docstrings dos módulos
2. Hook de pre-commit que regenera o mapa automaticamente
3. Comentário `# @module: <descrição>` na primeira linha de cada arquivo,
   usado pelo gerador

O mapa manual é um anti-pattern dado o princípio de que "ferramentas são a lei" (§1).
```

---

### F08 — Fluxo Determinístico de 11 Passos Sem Bypass

**Cláusula afetada:** §19 (Fluxo de Geração Determinístico)

**O problema:**  
O fluxo prescreve 11 passos (0 a 10) para toda implementação. Para mudanças triviais (ex: corrigir um typo em uma string de erro, ajustar um timeout em `.env`), executar todos os 11 passos é desproporcionalmente burocrático.

**Por que falha:**  
Não há critério de proporcionalidade. A ausência de uma classificação de mudanças (trivial/menor/maior/estrutural) faz com que o fluxo seja ignorado na prática para mudanças pequenas — criando um precedente de descumprimento que enfraquece todas as cláusulas.

**Solução proposta:**

```markdown
### §19.1 — Classificação de Mudanças

| Tipo       | Critério                                       | Passos Obrigatórios        |
| ---------- | ---------------------------------------------- | -------------------------- |
| Trivial    | Config, typos, constantes                      | 6 (mypy) + 10 (executar)   |
| Menor      | Lógica em ≤2 arquivos, sem mudança de contrato | 3-6 + 10                   |
| Maior      | Novo feature, novo adapter                     | Todos (0-10)               |
| Estrutural | Mudança de Protocol, migração                  | Todos + Impact Graph (§26) |
```

---

### F09 — STRICT_MODE Crash em Produção Sem Rollback

**Cláusula afetada:** §25 (Integridade Radical em Transições)

**O problema:**  
A cláusula determina que com `STRICT_ARCHITECTURE_MODE=true`, falhas em sistemas secundários disparam **exceções bloqueantes (crash)**. Em produção, crash sem estratégia de rollback significa:
1. **Indisponibilidade total** do serviço
2. **Perda potencial de dados** em operações parcialmente completadas
3. **Sem mecanismo de recuperação** prescrito

**Por que falha:**  
O princípio de "integridade sobre disponibilidade" é correto, mas a implementação de "crash e silêncio" é ingênua. Um crash sem circuit breaker, sem retry com backoff, e sem notificação é **pior** que degradação controlada — pode causar perda de dados irrecuperável se o crash ocorrer no meio de uma transação.

**Solução proposta:**

```markdown
### §25.1 — Estratégia de Crash Controlado

STRICT_MODE não significa "crash e morra". Significa "crash controlado":

1. **Antes do crash:** Persistir estado atual em `logs/crash_state.json`
   com contexto completo da operação em andamento
2. **Notificação:** Emitir alerta (log ERROR + mecanismo de notificação 
   configurado em .env)
3. **Idempotência:** Toda operação de escrita deve ser idempotente,
   permitindo replay seguro após crash
4. **Circuit Breaker:** Após N falhas consecutivas em sistema secundário
   (configurável via .env), o sistema entra em modo "manutenção" 
   (rejeita novas operações) em vez de crashar repetidamente
```

---

### F10 — mypy --strict Sem Enforcement Automatizado

**Cláusula afetada:** §1 (Excelência Estrutural Verificável)

**O problema:**  
A cláusula exige `mypy --strict` mas não prescreve:
1. Quando é executado (CI? pre-commit? manualmente?)
2. O que acontece se o projeto crescer com violações acumuladas
3. Como lidar com dependências externas sem stubs (`py.typed`)

**Por que falha:**  
O princípio "ferramentas são a lei" implica automação. Mas a cláusula não define **onde e quando** a ferramenta é executada automaticamente. Sem enforcement em CI/pre-commit, é uma sugestão, não uma lei.

**Solução proposta:**

```markdown
### §1.1 — Pipeline de Enforcement

Validação automática é obrigatória em pelo menos um destes pontos:
1. **Pre-commit hook** (preferido para feedback rápido)
2. **CI pipeline** (obrigatório se o projeto tem CI)
3. **Script `check_all.bat`** (mínimo aceitável)

Para dependências sem stubs:
- Usar `# type: ignore[import-untyped]` com comentário explicativo
- Manter lista de exceções em `mypy.ini` sob seção `[mypy-<package>]`
- Exceções devem ser revisadas a cada release
```

---

### F11 — Dois Padrões de Erro Sobrepostos

**Cláusulas afetadas:** §10 (Result Pattern) vs §24 (Erros com Semântica Formal)

**O problema:**  
A §10 define `Result[T, E] = Union[Success[T], Failure[E]]` com `E` como tipo genérico. A §24 define `DomainError` como Protocol com `code` e `message`. Não está claro:
1. O `E` do Result **deve** implementar `DomainError`?
2. Pode-se usar `Enum` como `E` (como no exemplo da §10: `OrderCreationError.EMPTY_CART`) **sem** `code` e `message`?
3. Qual é a hierarquia: `Result[Order, OrderCreationError]` onde `OrderCreationError` é Enum, ou `Result[Order, DomainError]` onde `DomainError` é Protocol?

**Por que falha:**  
Dois padrões de erro não conectados explicitamente geram implementações inconsistentes. Desenvolvedores diferentes (ou a IA em diferentes sessões) farão escolhas diferentes.

**Solução proposta:**

```markdown
### §10/§24 — Unificação de Padrões de Erro

Todo tipo de erro usado como `E` em `Result[T, E]` DEVE implementar 
o Protocol `DomainError`:

@dataclass(frozen=True)
class OrderCreationError:
    code: str
    message: str

    EMPTY_CART = ("ORDER_EMPTY_CART", "Cannot create order from empty cart")
    
    @classmethod
    def empty_cart(cls) -> "OrderCreationError":
        return cls(code="ORDER_EMPTY_CART", message="Cannot create order from empty cart")

# Uso no Result:
Result[Order, OrderCreationError]  # OrderCreationError satisfaz DomainError Protocol
```

---

### F12 — .env Sincronizado Sem Validação em Startup

**Cláusula afetada:** §12 (Configuração Externa e Zero Hardcoding)

**O problema:**  
A cláusula exige `.env` e `.env.example` sincronizados, mas não prescreve:
1. **Validação em startup** que verifique se todas as variáveis de `.env.example` existem em `.env`
2. **Tipos esperados** para cada variável
3. **Valores default** aceitáveis vs obrigatórios

**Por que falha:**  
Sincronização manual entre dois arquivos é exatamente o tipo de tarefa que humanos e IAs esquecem. Sem validação automatizada em startup, a regra é decorativa.

**Solução proposta:**

```markdown
### §12.1 — Validação de Configuração em Startup

O ponto de entrada do aplicativo DEVE validar configuração antes 
de qualquer operação:

1. Usar `pydantic.BaseSettings` (ou equivalente) com tipos explícitos
2. Toda variável tem tipo, default (se opcional) e descrição
3. Startup falha IMEDIATAMENTE se variável obrigatória está ausente
4. Script `scripts/validate_env.py` gera `.env.example` a partir 
   da classe Settings (single source of truth)
```

---

### F13 — Mapa de Contexto Manualmente Atualizado é Insustentável

**Cláusula afetada:** §23 (Mapa de Contexto do Projeto)

**O problema:**  
A cláusula exige:
> *"Toda criação/deleção de arquivo deve atualizar o mapa"*

Isso depende de disciplina humana ou da IA para uma tarefa puramente mecânica.

**Por que falha:**  
Contradiz diretamente o princípio fundamental: "ferramentas são a lei" e "validada por ferramentas automatizadas, não por revisão humana" (§1). Delegar uma tarefa mecânica a processo manual é inconsistente com a filosofia do próprio documento.

**Solução:** Já detalhada em F07. Automatizar geração do mapa.

---

### F14 — Exceção de "Fase de Descoberta" Cria Zona Cinzenta

**Cláusula afetada:** §14 (Contratos Antes de Comportamento)

**O problema:**  
A cláusula permite código "sujo" em `sandbox/` ou `explorations/`, marcado como descartável, para exploração de APIs externas. Mas não define:
1. **Prazo máximo** para o código exploratório existir
2. **Critério de conclusão** da fase de descoberta
3. **Quem decide** quando o código deve ser promovido ou deletado
4. **Proteção contra integração acidental** (gitignore? lint rule?)

**Por que falha:**  
Na prática, código "temporário" tende a se tornar permanente. Sem mecanismo de expiração ou enforcement, `sandbox/` acumula código não-conforme indefinidamente, servindo como escape valve para toda cláusula desconfortável.

**Solução proposta:**

```markdown
### §14.1 — Governança de Código Exploratório

1. `sandbox/` é listado no `.gitignore` por padrão
2. Código exploratório tem PRAZO MÁXIMO de 5 dias úteis (rastreado via 
   comentário `# @exploration-deadline: YYYY-MM-DD` na primeira linha)
3. Script `scripts/check_explorations.py` falha se existem arquivos 
   expirados em `sandbox/`
4. Promoção para `src/` exige: Protocol criado, testes escritos, 
   tutorial de extensibilidade (§16)
```

---

## Resumo de Impacto

```
┌─────────────────────────────────────────────────────────┐
│               MAPA DE INCONSISTÊNCIAS                    │
│                                                          │
│  §4 ←──contradiz──→ §20                                 │
│  §6 ←──contradiz──→ §20                                 │
│  §7 ←──conflita───→ §10                                 │
│  §10 ←─sobrepõe──→ §24                                  │
│  §1  ←─contradiz──→ §23 (ferramentas vs manual)         │
│  §8 + §5 ──────────→ §23 (explosão → manutenção)       │
│  §14 ────escape────→ todas (zona cinzenta)              │
│  §2, §12, §17 ─────→ sem enforcement automatizado       │
│  §25 ──────────────→ crash sem safety net                │
│  §19 ──────────────→ sem proporcionalidade               │
└─────────────────────────────────────────────────────────┘
```

---

## Recomendação Geral

As Cláusulas Pétreas são um documento de alta qualidade com princípios sólidos. As falhas identificadas não são de princípio, mas de **precisão operacional**. As correções se agrupam em 3 ações macro:

1. **Resolver contradições §4/§6 vs §20:** Definir hierarquia explícita entre Protocol-First e YAGNI baseada no tipo de componente (I/O vs domínio puro).

2. **Automatizar o que é prescrito como manual:** Mapa de contexto (§23), sincronização de `.env` (§12), validação mypy (§1), e expiração de explorações (§14) devem ser implementados como ferramentas, não como disciplina humana.

3. **Adicionar proporcionalidade:** O fluxo determinístico (§19), o monitoramento (§2), e o STRICT_MODE (§25) precisam de critérios de escala que adaptem rigor ao tamanho da mudança.

---

> *"A excelência de regras fixas depende da ausência de contradições internas. Cláusulas que se anulam mutuamente criam arbítrio, o oposto do determinismo que buscam."*
