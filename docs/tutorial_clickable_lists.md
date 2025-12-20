# Guia de Implementação: Listas Clicáveis no Telegram

Este guia explica como transformar listas de texto estático em botões interativos no Telegram, usando como exemplo a funcionalidade de listar arquivos (`/list`).

## O Problema

Originalmente, o comando `/list` exibia os arquivos assim:

```text
📂 Session 2025-12-20_14-41-38
• 01_constitution.md
• 02_specification.md

💡 Use /get <path> to download a file.
```

O usuário precisava copiar o caminho e digitar `/get transcripts/01_constitution.md`. Isso é ruim para a experiência do usuário (UX).

## A Solução: Botões Inline

Transformamos cada item da lista em um botão que, ao ser clicado, dispara a ação de download automaticamente.

### 1. Criar o Construtor do Teclado

Primeiro, precisamos de uma função que receba a lista de dados (arquivos, sessões, etc.) e retorne um objeto `InlineKeyboardMarkup`.

**Arquivo:** `src/services/telegram/keyboards.py`

```python
def build_file_list_keyboard(files: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """
    Constrói um teclado onde cada botão baixa um arquivo.
    
    Args:
        files: Lista de tuplas (emoji, caminho_relativo, tamanho_bytes)
    """
    buttons = []
    for emoji, path, size in files:
        # O rótulo do botão (o que o usuário vê)
        display_name = path.split('/')[-1]
        label = f"{emoji} {display_name}"
        
        # O dado enviado de volta quando clicado (invisível ao usuário)
        # Formato: action:<tipo>:<valor>
        callback_data = f"action:get_file:{path}"
        
        # Importante: Telegram limita callback_data a 64 bytes!
        if len(callback_data.encode('utf-8')) > 64:
            continue # Ignora arquivos com caminhos muito longos
            
        buttons.append([
            InlineKeyboardButton(label, callback_data=callback_data)
        ])
    
    return InlineKeyboardMarkup(buttons)
```

### 2. Atualizar o Comando de Listagem

Altere o comando que exibe a lista para usar o novo teclado.

**Arquivo:** `src/cli/daemon.py` (Método `_cmd_list`)

```python
# ... lógica para obter a lista de arquivos ...

# Importe o construtor
from src.services.telegram.keyboards import build_file_list_keyboard

# Construa o teclado
keyboard = build_file_list_keyboard(files)

# Envie a mensagem com o teclado
await self.bot.send_message(
    event.chat_id,
    f"📂 *{session_name}*\n"
    # ... texto da mensagem ...
    "\n\n👇 Clique em um arquivo para baixar:",
    parse_mode="Markdown",
    reply_markup=keyboard, # <--- AQUI
)
```

### 3. Tratar o Clique (Callback)

Quando o usuário clica, o Telegram envia um evento de callback. Precisamos capturá-lo e executar a ação.

**Arquivo:** `src/cli/daemon.py` (Método `_handle_action_callback`)

```python
    async def _handle_action_callback(self, event: TelegramEvent, action: str) -> None:
        # ... outros handlers ...
        
        elif action.startswith("get_file:"):
            # Extrai o caminho do arquivo do callback (remove o prefixo "get_file:")
            file_path = action.split(":", 1)[1]
            
            # Simula o comando /get com o caminho
            # NOTA: Não modifique event.command_args diretamente (é somente leitura)
            # Em vez disso, passe o argumento via override_args
            await self._cmd_get(event, override_args=file_path)
```

## Resumo

1.  **Keyboards (`keyboards.py`):** Crie uma função que itera sobre seus dados e cria `InlineKeyboardButton`s.
2.  **Comando (`daemon.py`):** Gere o teclado e anexe-o à mensagem com `reply_markup`.
3.  **Callback (`daemon.py`):** Adicione um `elif` no handler de callbacks para processar a ação do botão.

## Dicas Importantes

*   **Limite de 64 bytes:** O `callback_data` é muito limitado. Se seus IDs ou caminhos forem longos, você precisará de uma estratégia de mapeamento (ex: salvar o caminho em um dicionário temporário e enviar apenas um ID curto no botão).
*   **UX:** Sempre dê um feedback visual. O usuário clica e espera algo acontecer.
*   **Segurança:** Valide os dados recebidos no callback da mesma forma que validaria um comando de texto.
