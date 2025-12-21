# Tutorial: Pipeline de Prompts

Este guia explica como os prompts do pipeline de narrativa são construídos e como adicionar novos steps ao início do pipeline.

## Visão Geral da Arquitetura

O pipeline de narrativa transforma texto caótico (brainstorm) em artefatos estruturados. Cada step do pipeline:

1. Recebe variáveis de contexto (input original + artefatos anteriores)
2. Renderiza um template de prompt com essas variáveis
3. Envia ao LLM e armazena o resultado como um novo artefato
4. O artefato fica disponível como contexto para os steps seguintes

## Arquivos Envolvidos

```
src/services/orchestrator.py    # Define a sequência de steps (STEPS)
src/lib/prompts.py              # Carrega e renderiza templates
prompts/*.md                    # Templates de prompt
```

## Como Funciona o Pipeline

### 1. Definição dos Steps

No arquivo [orchestrator.py](../src/services/orchestrator.py), a constante `STEPS` define a sequência:

```python
STEPS = [
    PipelineStep(number=1, name="semantic_normalization", prompt_template="semantic_normalization"),
    PipelineStep(number=2, name="constitution", prompt_template="constitution"),
    PipelineStep(number=3, name="specification", prompt_template="specification"),
    PipelineStep(number=4, name="planning", prompt_template="planning"),
    PipelineStep(number=5, name="tasks", prompt_template="tasks"),
]
```

Cada `PipelineStep` possui:

- **number**: Número sequencial do step (1-indexed, contíguo)
- **name**: Nome semântico usado para identificar o artefato
- **prompt_template**: Nome do arquivo de template (sem `.md`)

### 2. Injeção de Variáveis

O método `_build_prompt()` injeta variáveis no template:

```python
def _build_prompt(self, step: PipelineStep) -> str:
    # Step 1: só recebe o input original
    variables = {
        "input_content": self._input.content,
    }

    # Steps seguintes recebem artefatos anteriores
    if step.number >= 2 and 1 in self._artifacts:
        variables["semantic_normalization"] = self._artifacts[1].content

    if step.number >= 3 and 2 in self._artifacts:
        variables["constitution_content"] = self._artifacts[2].content
    
    # ... e assim por diante
```

### 3. Sintaxe do Template

Templates usam a sintaxe `{{ nome_variavel }}` para placeholders:

```markdown
# Meu Prompt

## Dados de Entrada

[[[INPUT_START]]]
{{ input_content }}
[[[INPUT_END]]]
```

O `PromptLoader` converte `{{ var }}` para `$var` internamente e faz a substituição.

## Adicionando um Step no Início do Pipeline

### Passo 1: Criar o Template do Prompt

Crie um arquivo em `prompts/` com o template. O primeiro step deve usar `{{ input_content }}` como única variável:

```markdown
# prompts/meu_novo_step.md

# Meu Novo Processador

[Instruções do prompt...]

## Dados de Entrada

[[[BRAINSTORM_START]]]
{{ input_content }}
[[[BRAINSTORM_END]]]
```

### Passo 2: Atualizar a Lista de Steps

Em [orchestrator.py](../src/services/orchestrator.py), adicione o novo step no início e renumere os demais:

```python
STEPS = [
    PipelineStep(number=1, name="meu_novo_step", prompt_template="meu_novo_step"),
    PipelineStep(number=2, name="constitution", prompt_template="constitution"),
    PipelineStep(number=3, name="specification", prompt_template="specification"),
    # ...
]
```

### Passo 3: Atualizar _build_prompt()

Ajuste o método para:

1. Passar `input_content` para o step 1 (seu novo step)
2. Passar o artefato do step 1 para os steps seguintes
3. Ajustar os números de todos os steps

```python
def _build_prompt(self, step: PipelineStep) -> str:
    variables = {
        "input_content": self._input.content,
    }

    # Step 2+ recebe o artefato do step 1
    if step.number >= 2 and 1 in self._artifacts:
        variables["meu_novo_step"] = self._artifacts[1].content

    # Step 3+ recebe o artefato do step 2
    if step.number >= 3 and 2 in self._artifacts:
        variables["constitution_content"] = self._artifacts[2].content
    
    # ... ajustar todos os números
```

### Passo 4: Atualizar Prompts Existentes

Substitua `{{ input_content }}` por `{{ meu_novo_step }}` em todos os prompts que agora devem consumir o artefato do novo step ao invés do input original:

**Antes (constitution.md):**
```markdown
{{ input_content }}
```

**Depois (constitution.md):**
```markdown
{{ meu_novo_step }}
```

### Passo 5: Atualizar Testes Unitários

Em [test_orchestrator.py](../tests/unit/test_orchestrator.py), ajuste os testes que verificam:

- Qual step é o primeiro (`test_constitution_is_first` → `test_novo_step_is_first`)
- Contagem total de steps
- Contiguidade dos números

## Exemplo Completo: Adicionando Semantic Normalization

### Template: prompts/semantic_normalization.md

```markdown
# Role
You are a Semantic Normalization System...

## Input Data

### 1. BRAINSTORM
[[[BRAINSTORM_START]]]
{{ input_content }}
[[[BRAINSTORM_END]]]
```

### Orchestrator: STEPS

```python
STEPS = [
    PipelineStep(number=1, name="semantic_normalization", prompt_template="semantic_normalization"),
    PipelineStep(number=2, name="constitution", prompt_template="constitution"),
    PipelineStep(number=3, name="specification", prompt_template="specification"),
    PipelineStep(number=4, name="planning", prompt_template="planning"),
    PipelineStep(number=5, name="tasks", prompt_template="tasks"),
]
```

### Orchestrator: _build_prompt()

```python
def _build_prompt(self, step: PipelineStep) -> str:
    variables = {
        "input_content": self._input.content,
    }

    if step.number >= 2 and 1 in self._artifacts:
        variables["semantic_normalization"] = self._artifacts[1].content

    if step.number >= 3 and 2 in self._artifacts:
        variables["constitution_content"] = self._artifacts[2].content

    if step.number >= 4 and 3 in self._artifacts:
        variables["specification_content"] = self._artifacts[3].content

    if step.number >= 5 and 4 in self._artifacts:
        variables["planning_content"] = self._artifacts[4].content

    return load_prompt(step.prompt_template, **variables)
```

### Prompts Atualizados

Todos os prompts do step 2 em diante usam `{{ semantic_normalization }}` ao invés de `{{ input_content }}`:

- **constitution.md**: `{{ semantic_normalization }}`
- **specification.md**: `{{ semantic_normalization }}`
- **planning.md**: `{{ semantic_normalization }}`
- **tasks.md**: `{{ semantic_normalization }}`

## Checklist de Validação

Após fazer as alterações, valide:

- [ ] Template do novo step criado em `prompts/`
- [ ] Step adicionado em `STEPS` com número correto
- [ ] Números dos steps contíguos (1, 2, 3...)
- [ ] `_build_prompt()` atualizado com novas variáveis
- [ ] Prompts existentes atualizados para usar nova variável
- [ ] Testes unitários atualizados (ex: `test_constitution_is_first` → `test_semantic_normalization_is_first`)
- [ ] Testes unitários passando: `pytest tests/unit/test_orchestrator.py -v`

## Troubleshooting

### Erro: "Prompt template not found"

Verifique se o arquivo `.md` existe em `prompts/` com o nome exato do `prompt_template`.

### Erro: Variável não substituída (aparece `{{ var }}` no output)

Verifique se:
1. A variável está sendo passada em `_build_prompt()`
2. O nome da variável no dicionário corresponde exatamente ao placeholder no template
3. O step anterior foi executado e produziu um artefato

### Testes falhando após adicionar step

Ajuste os testes em `test_orchestrator.py`:
- `test_constitution_is_first` → verificar novo primeiro step
- `test_tasks_is_last` → verificar que tasks ainda é o último
- `test_step_numbers_contiguous` → deve passar automaticamente se números estiverem corretos
