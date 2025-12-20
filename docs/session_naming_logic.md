# Lógica de Nomenclatura de Sessões (`intelligible_name`)

Este documento descreve como o campo `intelligible_name` é gerado e atualizado no ciclo de vida de uma sessão, e como alterar essa lógica.

## Visão Geral

O `intelligible_name` é um nome legível para humanos atribuído a uma sessão. Ele passa por dois estágios principais:

1.  **Criação (Fallback):** Um nome baseado em data/hora é gerado quando a sessão é criada.
2.  **Atualização (Contextual):** O nome é atualizado com base no conteúdo da transcrição assim que o primeiro áudio é processado.

## 1. Criação Inicial (Nome Padrão)

Quando uma sessão é criada, ela recebe um nome padrão para não ficar vazia ou apenas com o ID técnico.

*   **Arquivo:** `src/services/session/manager.py`
*   **Método:** `_create_session_internal`
*   **Lógica:**
    1.  Chama `get_name_generator().generate_fallback_name(created_at)`.
    2.  O gerador padrão (`DefaultNameGenerator` em `src/services/session/name_generator.py`) retorna algo como "Áudio de {dia} de {mês}".
    3.  O `SessionManager` garante que o nome seja único adicionando um sufixo se necessário (ex: "Áudio de 20 de Dezembro (2)").

### Como Alterar o Nome Padrão

Para mudar o formato do nome inicial (ex: mudar para "Sessão - 20/12"), edite o método `generate_fallback_name` em `src/services/session/name_generator.py`:

```python
# src/services/session/name_generator.py

def generate_fallback_name(self, created_at: datetime) -> str:
    """Generate Portuguese timestamp-based fallback name."""
    # Exemplo de alteração:
    return f"Sessão - {created_at.strftime('%d/%m/%Y %H:%M')}"
```

## 2. Atualização Pós-Transcrição

Assim que o primeiro áudio da sessão é transcrito com sucesso, o sistema tenta gerar um nome mais descritivo baseado no conteúdo falado.

*   **Arquivo:** `src/cli/daemon.py`
*   **Método:** `_run_transcription`
*   **Lógica:**
    1.  Verifica se é o primeiro áudio (`audio_entry.sequence == 1`).
    2.  Chama `name_generator.generate_from_transcript(result.text)`.
    3.  Se um nome válido for gerado, chama `self.session_manager.update_session_name`.

### Como Alterar a Lógica de Extração

A lógica que decide quais palavras usar do texto está em `src/services/session/name_generator.py`, no método `generate_from_transcript`.

Atualmente, ela:
1.  Remove "filler words" (palavras de preenchimento como "um", "tipo", "então").
2.  Exige um mínimo de palavras significativas (`MIN_MEANINGFUL_WORDS`).
3.  Limita o tamanho do nome (`MAX_WORDS_FROM_TRANSCRIPT`).

Para alterar isso (ex: aumentar o número de palavras ou mudar a lista de stop words), edite a classe `DefaultNameGenerator`:

```python
# src/services/session/name_generator.py

class DefaultNameGenerator(NameGenerator):
    MAX_NAME_LENGTH = 100
    MIN_MEANINGFUL_WORDS = 2
    MAX_WORDS_FROM_TRANSCRIPT = 5  # Aumente aqui para nomes mais longos

    def generate_from_transcript(self, transcript: str) -> Optional[str]:
        # ... lógica de filtragem ...
```

## Resumo dos Arquivos Envolvidos

| Funcionalidade | Arquivo | Método/Classe |
| :--- | :--- | :--- |
| **Gerador de Nomes** | `src/services/session/name_generator.py` | `DefaultNameGenerator` |
| **Aplicação na Criação** | `src/services/session/manager.py` | `_create_session_internal` |
| **Gatilho de Atualização** | `src/cli/daemon.py` | `_run_transcription` |
| **Persistência da Atualização** | `src/services/session/manager.py` | `update_session_name` |
