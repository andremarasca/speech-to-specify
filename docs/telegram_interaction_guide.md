# Guia de Alteração da Interação Telegram: Adicionando Botões

Este relatório descreve os passos necessários para alterar a interação do bot Telegram, especificamente substituindo sugestões de texto por botões interativos. Usaremos como exemplo a adição de um botão "Ver todas as sessões" na resposta do comando `/reopen`.

## Visão Geral da Arquitetura

A interação do Telegram é dividida em três partes principais:
1.  **Mensagens e Textos (`src/lib/messages.py`)**: Define todos os textos e rótulos de botões.
2.  **Teclados e Botões (`src/services/telegram/keyboards.py`)**: Constrói os objetos de interface (InlineKeyboards).
3.  **Lógica do Bot (`src/cli/daemon.py`)**: Gerencia comandos, envia mensagens e processa os cliques nos botões (callbacks).

---

## Passo a Passo para Implementação

### 1. Definir o Rótulo do Botão

Primeiro, devemos externalizar o texto do botão para manter o suporte a múltiplos idiomas e configurações de interface.

**Arquivo:** `src/lib/messages.py`

Adicione as constantes para o novo botão na seção de botões:

```python
# ... outros botões ...
BUTTON_SESSIONS_LIST = "📋 Ver todas as sessões"
BUTTON_SESSIONS_LIST_SIMPLIFIED = "Ver todas as sessões"
```

### 2. Criar o Construtor do Teclado

Crie uma função para construir o teclado que conterá o botão.

**Arquivo:** `src/services/telegram/keyboards.py`

1.  Importe as novas constantes de mensagem:
    ```python
    from src.lib.messages import (
        # ...
        BUTTON_SESSIONS_LIST,
        BUTTON_SESSIONS_LIST_SIMPLIFIED,
    )
    ```

2.  Adicione uma nova função construtora (pode ser no final do arquivo ou junto com os outros builders):

    ```python
    def build_sessions_list_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
        """Constrói teclado com link para listar sessões."""
        label = BUTTON_SESSIONS_LIST_SIMPLIFIED if simplified else BUTTON_SESSIONS_LIST
        
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data="action:list_sessions")]
        ])
    ```

### 3. Implementar a Ação do Botão (Callback)

Quando o usuário clica no botão, o Telegram envia um "callback" com os dados definidos (`action:list_sessions`). Precisamos ensinar o bot a reagir a isso.

**Arquivo:** `src/cli/daemon.py`

Localize o método `_handle_action_callback` e adicione o tratamento para a nova ação:

```python
    async def _handle_action_callback(self, event: TelegramEvent, action: str) -> None:
        """Handle action: callbacks."""
        if action == "finalize":
            # ... código existente ...
        
        # ADICIONE ESTE BLOCO:
        elif action == "list_sessions":
            # Executa a mesma lógica do comando /sessions
            await self._cmd_sessions(event)
            
        # ... restante do código ...
```

### 4. Atualizar o Comando `/reopen`

Finalmente, altere o comando para enviar o teclado junto com a mensagem.

**Arquivo:** `src/cli/daemon.py`

1.  Importe o novo builder no início do método ou do arquivo:
    ```python
    from src.services.telegram.keyboards import build_sessions_list_keyboard
    ```

2.  Localize o método `_cmd_reopen` e a parte onde a mensagem de erro é enviada. Substitua o código:

    **Código Antigo:**
    ```python
    await self.bot.send_message(
        event.chat_id,
        "❌ Nenhuma sessão disponível para reabrir.\n\n"
        "💡 /sessions para ver todas as sessões.",
        parse_mode="Markdown",
    )
    ```

    **Novo Código:**
    ```python
    # Constrói o teclado (respeitando a preferência de UI simplificada)
    keyboard = build_sessions_list_keyboard(simplified=self._simplified_ui)

    await self.bot.send_message(
        event.chat_id,
        "❌ Nenhuma sessão disponível para reabrir.",
        parse_mode="Markdown",
        reply_markup=keyboard,  # Adiciona o botão aqui
    )
    ```

---

## Resumo das Alterações

| Arquivo | Alteração | Propósito |
|---------|-----------|-----------|
| `src/lib/messages.py` | Adicionar `BUTTON_SESSIONS_LIST` | Definir o texto do botão. |
| `src/services/telegram/keyboards.py` | Adicionar `build_sessions_list_keyboard` | Criar o objeto visual do botão. |
| `src/cli/daemon.py` | Atualizar `_handle_action_callback` | Fazer o botão funcionar (executar ação). |
| `src/cli/daemon.py` | Atualizar `_cmd_reopen` | Exibir o botão para o usuário. |
