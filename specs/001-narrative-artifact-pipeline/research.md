# Research: Constituidor de Artefatos Narrativos

**Feature**: 001-narrative-artifact-pipeline  
**Date**: 2025-12-18  
**Status**: Complete

## Research Tasks Completed

### 1. LLM Provider Abstraction Patterns

**Task**: Research best practices for LLM provider abstraction in Python

**Decision**: Protocol-based abstraction with adapter pattern

**Rationale**: 
- Python Protocols (PEP 544) permitem duck typing estrutural sem herança forçada
- Cada provedor implementa o mesmo contrato, permitindo troca via configuração
- Padrão já consolidado em bibliotecas como LangChain e LiteLLM

**Alternatives Considered**:
- ABC (Abstract Base Class): Mais rígido, exige herança explícita. Rejeitado por coupling desnecessário.
- Função factory com dict de provedores: Simples mas não documenta contrato. Rejeitado por falta de clareza.

**Implementation Notes**:
```python
from typing import Protocol

class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Send prompt and return completion text."""
        ...
    
    @property
    def provider_name(self) -> str:
        """Return provider identifier for logging."""
        ...
```

---

### 2. Persistence Strategy for Artifacts and Logs

**Task**: Research storage patterns for auditability requirements

**Decision**: File-based storage with JSON/JSONL formats

**Rationale**:
- Simplicidade: sem dependência de banco de dados
- Legibilidade: artefatos em Markdown, logs em JSONL (uma linha por evento)
- Backup trivial: copiar diretório
- Compatível com versionamento (git-friendly)

**Alternatives Considered**:
- SQLite: Overhead para caso de uso simples. Rejeitado por complexidade desnecessária.
- Pickle: Não legível, não auditável. Rejeitado por violar rastreabilidade.

**Implementation Notes**:
```
output/
├── executions/
│   └── {execution_id}/
│       ├── input.md           # Entrada original
│       ├── artifacts/
│       │   ├── 01_constitution.md
│       │   ├── 02_specification.md
│       │   └── 03_planning.md
│       ├── logs/
│       │   └── llm_traffic.jsonl
│       └── execution.json     # Metadados da execução
```

---

### 3. CLI Framework Selection

**Task**: Research CLI framework for Python

**Decision**: argparse (stdlib) para MVP, migração opcional para Typer/Click futuro

**Rationale**:
- Zero dependências externas
- Suficiente para interface simples (1-2 comandos)
- Extensibilidade futura não comprometida

**Alternatives Considered**:
- Click/Typer: Mais ergonômico, mas adiciona dependência. Rejeitado para MVP por YAGNI.
- Fire: Auto-generate CLI from functions. Rejeitado por magic behavior que viola determinismo.

---

### 4. Configuration Management

**Task**: Research env var and configuration patterns

**Decision**: python-dotenv + pydantic Settings

**Rationale**:
- dotenv carrega .env em desenvolvimento
- pydantic valida e tipifica configuração
- Falha explícita se variável obrigatória ausente

**Alternatives Considered**:
- os.environ direto: Sem validação, sem defaults tipados. Rejeitado por fragilidade.
- TOML/YAML config files: Mais complexo que necessário. Rejeitado por YAGNI.

**Implementation Notes**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    output_dir: str = "output"
    
    class Config:
        env_file = ".env"
```

---

### 5. HTTP Client for LLM APIs

**Task**: Research HTTP client options for API calls

**Decision**: httpx (sync mode)

**Rationale**:
- API moderna, type hints completos
- Suporte a timeout configurável
- Não requer async para caso de uso síncrono
- Melhor error handling que requests

**Alternatives Considered**:
- requests: Popular mas API antiga, sem type hints nativos. Aceitável como fallback.
- aiohttp: Async-only, complexidade desnecessária para fluxo sequencial.

---

### 6. Timestamp and ID Generation

**Task**: Research deterministic identification strategy

**Decision**: UUID4 para IDs únicos, ISO 8601 para timestamps

**Rationale**:
- UUID4 garante unicidade sem coordenação
- ISO 8601 é padrão internacional, sortable, timezone-aware
- Ambos são determinísticos dado o momento de criação

**Implementation Notes**:
```python
from datetime import datetime, timezone
from uuid import uuid4

def generate_id() -> str:
    return str(uuid4())

def generate_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
```

---

### 7. Error Handling and Failure Recovery

**Task**: Research patterns for graceful degradation

**Decision**: Exception hierarchy + explicit failure states

**Rationale**:
- Hierarquia permite catch seletivo (LLMError vs ValidationError)
- Estado de falha persistido antes de propagar exceção
- Artefatos parciais sempre preservados

**Implementation Notes**:
```python
class NarrativeError(Exception):
    """Base exception for narrative pipeline."""
    pass

class LLMError(NarrativeError):
    """LLM provider communication error."""
    pass

class ValidationError(NarrativeError):
    """Input or artifact validation error."""
    pass
```

---

### 8. Testing Strategy

**Task**: Research testing patterns for LLM-dependent code

**Decision**: Fixture-based mocking + contract tests

**Rationale**:
- LLM responses mockadas com fixtures determinísticas
- Contract tests validam que adaptadores implementam Protocol corretamente
- Integration tests usam fixtures, não APIs reais

**Implementation Notes**:
```python
# conftest.py
@pytest.fixture
def mock_llm_provider():
    class MockProvider:
        provider_name = "mock"
        def complete(self, prompt: str) -> str:
            return f"Mock response for: {prompt[:50]}..."
    return MockProvider()
```

---

## Decisions Summary

| Area | Decision | Key Dependency |
|------|----------|----------------|
| LLM Abstraction | Protocol + Adapters | typing.Protocol |
| Persistence | File-based (JSON/JSONL/MD) | None (stdlib) |
| CLI | argparse | None (stdlib) |
| Config | pydantic-settings + dotenv | pydantic, python-dotenv |
| HTTP | httpx (sync) | httpx |
| IDs | UUID4 + ISO 8601 | None (stdlib) |
| Errors | Exception hierarchy | None (stdlib) |
| Testing | pytest + fixtures | pytest |

## Dependencies List

```
# requirements.txt
pydantic>=2.0
pydantic-settings>=2.0
python-dotenv>=1.0
httpx>=0.25

# requirements-dev.txt
pytest>=8.0
pytest-cov>=4.0
```

## Open Questions Resolved

1. **Q**: Usar async ou sync para chamadas LLM?  
   **A**: Sync. Fluxo é sequencial por definição, async adiciona complexidade sem benefício.

2. **Q**: Como estruturar os prompts?  
   **A**: Arquivos Markdown em `/prompts/` com placeholders explícitos. Versionáveis com código.

3. **Q**: Onde persistir execuções?  
   **A**: Diretório `output/` configurável, estrutura hierárquica por execution_id.

4. **Q**: Como garantir determinismo com LLMs não-determinísticos?  
   **A**: Determinismo da cadeia, não do conteúdo. Mesma entrada → mesma sequência de etapas. Conteúdo varia por natureza do LLM, mas fluxo e registro são determinísticos.
