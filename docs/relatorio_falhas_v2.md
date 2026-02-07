# Relatório de Falhas — Cláusulas Pétreas v2

> **Data:** 2026-02-07
> **Escopo:** Análise das cláusulas pós-correção. Foco em falhas residuais que exigem automação real ou ajuste textual. Cada falha acompanha (quando aplicável) o script portável correspondente em `scripts/`.

---

## Critério de Seleção

Falhas incluídas neste relatório atendem a pelo menos um destes critérios:

1. **Regra não-verificável** — prescreve algo que nenhuma ferramenta valida automaticamente
2. **Prescrição sem implementação de referência** — menciona artefatos (`generate_map.py`, `validate_env.py`) que não existem em nenhum lugar; sem código de referência, cada projeto reinventa a roda
3. **Lacuna lógica** — omite cenários comuns que causam ambiguidade operacional
4. **Inconsistência interna residual** — cláusulas que ainda se contradizem após correções anteriores

---

## Índice

| #   | Cláusula | Tipo              | Título                                                         |      Script gerado?       |
| --- | -------- | ----------------- | -------------------------------------------------------------- | :-----------------------: |
| F01 | §5       | Não-verificável   | Regras de importação declaradas mas sem enforcement            |   ✅ `check_imports.py`    |
| F02 | §8       | Não-verificável   | Limite de 200 linhas declarado mas sem enforcement             |  ✅ `check_file_sizes.py`  |
| F03 | §23      | Sem implementação | `generate_map.py` citado mas nunca fornecido                   |    ✅ `generate_map.py`    |
| F04 | §12      | Sem implementação | `validate_env.py` citado mas nunca fornecido                   |    ✅ `validate_env.py`    |
| F05 | §14      | Sem implementação | `check_explorations.py` citado mas nunca fornecido             | ✅ `check_explorations.py` |
| F06 | §1       | Sem implementação | `check_all` citado como mínimo mas sem script modelo           |     ✅ `check_all.py`      |
| F07 | §10/§24  | Sem implementação | Result e DomainError prescritos mas sem código portável        |   ✅ `shared/result.py`    |
| F08 | §21      | Lacuna            | Convenção de nomes não cobre `__init__.py`, configs e testes   |         ✅ textual         |
| F09 | §3       | Lacuna            | Cobertura "obrigatória" sem percentual mínimo definido         |         ✅ textual         |
| F10 | §15      | Inconsistência    | Glossário como "alternativa" em código dilui a obrigatoriedade |         ✅ textual         |

---

## Análise Detalhada

### F01 — Regras de Importação Sem Enforcement (§5)

**O problema:**
A §5 declara regras de importação (`domain/` não importa nada externo, `ports/` importa apenas `domain/`, etc.) seguidas de "(validadas por ferramentas)". Contudo, nenhuma ferramenta é especificada e nenhum script é fornecido. A IA ou o desenvolvedor não tem como saber se violou a regra sem inspeção manual.

**Por que importa:**
Sem enforcement automatizado, as regras de importação se degradam silenciosamente. Um import de `adapters/` dentro de `domain/` passa despercebido até causar acoplamento irreversível.

**Solução:** Script `check_imports.py` (fornecido em `scripts/`) que valida as regras de importação em cada execução de `check_all`.

---

### F02 — Limite de Linhas Sem Enforcement (§8)

**O problema:**
A §8 define 200 linhas como limite e 250 como máximo aceitável. O projeto atual tem 18 arquivos acima do limite, com o pior caso em **3.415 linhas** (`daemon.py`). A regra existe há meses sem efeito prático.

**Solução:** Script `check_file_sizes.py` que emite warnings (>200) e erros (>300) com saída estruturada mostrando os piores ofensores.

---

### F03 — `generate_map.py` Prometido e Inexistente (§23)

**O problema:**
A §23 prescreve que o mapa é "gerado automaticamente por `scripts/generate_map.py`", mas o script nunca foi fornecido. Sem implementação de referência, cada projeto precisa criar o seu, violando o princípio de que a IA "segue convenção, não inventa".

**Solução:** Script portável fornecido. Lê docstrings de módulo, gera `docs/map.md`.

---

### F04 — `validate_env.py` Prometido e Inexistente (§12)

**O problema:**
A §12 diz que "`validate_env.py` gera `.env.example` a partir da classe Settings (single source of truth)". O script não existe. Sem ele, a sincronização `.env` ↔ `.env.example` é manual — exatamente o que a cláusula proíbe.

**Solução:** Script portável que inspeciona a classe `Settings` (pydantic `BaseSettings`) e gera `.env.example` automaticamente. Também valida que `.env` contém todas as variáveis obrigatórias.

---

### F05 — `check_explorations.py` Prometido e Inexistente (§14)

**O problema:**
A §14 prescreve `check_explorations.py` para verificar prazos de código exploratório em `sandbox/`. Sem o script, o mecanismo de governança é puramente declarativo.

**Solução:** Script portável fornecido.

---

### F06 — `check_all` Sem Script Modelo (§1)

**O problema:**
O Pipeline de Enforcement Obrigatório (§1) lista `check_all.bat` como "mínimo aceitável", e a §23 diz que `generate_map.py` é "executado como parte de `check_all`". Mas não existe nenhum `check_all` de referência que orquestre: mypy → pytest → check_imports → check_file_sizes → generate_map → validate_env → check_explorations.

**Solução:** Script orquestrador `check_all.py` (cross-platform, Python) + wrappers `.bat`/`.sh`.

---

### F07 — Result Pattern e DomainError Sem Código Portável (§10/§24)

**O problema:**
As §10 e §24 prescrevem `Success[T]`, `Failure[E]`, `Result = Union[Success[T], Failure[E]]` e `DomainError Protocol` como pilares fundamentais. Mas não existe implementação de referência portável. Cada projeto precisaria reimplementar o padrão, com risco de variações incompatíveis.

O Result prescrito nas cláusulas também não tem os métodos `.and_then()`, `.map()` que a §7 recomenda para manter CC baixo em pipelines.

**Solução:** Módulo `shared/result.py` portável com `Success`, `Failure`, `Result` e métodos de encadeamento. Também inclui o `DomainError` Protocol.

---

### F08 — Convenção de Nomenclatura Incompleta (§21)

**O problema:**
A §21 cobre Ports, Adapters, Services, UseCases, ValueObjects e Erros. Mas não cobre:
- `__init__.py` — quando deve ter imports explícitos vs estar vazio?
- `conftest.py` — convenção para fixtures compartilhadas
- Arquivos de configuração (`settings.py` vs `config.py` vs `configuration.py`)
- Nomes de módulos de teste (`test_create_user.py` vs `test_user_creation.py`)

**Impacto:** Baixo. A IA consegue inferir por contexto. Não justifica script.

**Solução textual:** Adicionar nota na §21 cobrindo as omissões mais relevantes.

---

### F09 — Cobertura de Testes Sem Percentual Mínimo (§3)

**O problema:**
A §3 diz "funções puras do domínio têm cobertura obrigatória" mas não define o que "cobertura obrigatória" significa em termos mensuráveis. É 80%? 100%? Apenas funções públicas?

**Impacto:** Médio. Sem métrica, "cobertura obrigatória" é subjetivo.

**Solução textual:** Definir cobertura mínima de linhas para `domain/` (sugestão: 90%) e incluir `--cov` no `check_all`.

---

### F10 — Glossário com "Alternativa" que Dilui Obrigatoriedade (§15)

**O problema:**
A §15 diz "manter `docs/glossary.md`" e oferece "alternativa: `src/shared/glossary.py`". Ter duas opções equivalentes sem critério de escolha cria ambiguidade — exatamente o que as cláusulas tentam eliminar.

**Solução textual:** Eliminar a alternativa. O glossário é `docs/glossary.md`. Se houver constantes em código, elas referenciam o glossário, não o substituem.

---

## Mapa de Scripts Gerados

```
scripts/
├── check_all.py              # Orquestrador: roda tudo em sequência (F06)
├── check_all.bat              # Wrapper Windows
├── check_all.sh               # Wrapper Unix
├── check_imports.py           # Valida regras de importação hexagonal (F01)
├── check_file_sizes.py        # Valida limite de linhas por arquivo (F02)
├── generate_map.py            # Gera docs/map.md a partir de docstrings (F03)
├── validate_env.py            # Gera .env.example e valida .env (F04)
├── check_explorations.py      # Verifica prazos de sandbox/ (F05)
└── shared/
    └── result.py              # Result[T,E], Success, Failure, DomainError (F07)
```

Todos os scripts são **zero-dependency** (stdlib pura) exceto `validate_env.py` que depende minimamente da existência de `pydantic-settings` no projeto alvo.
