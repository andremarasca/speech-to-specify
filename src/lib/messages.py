"""Externalized message templates for Telegram UI.

Per Constitution Principle V (Externalized Configuration):
All user-facing message templates are externalized here for
future localization support.

Per plan.md for 005-telegram-ux-overhaul.
Current language: Portuguese (pt-BR).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ui_state import KeyboardType

# =============================================================================
# Onboarding Messages (T080)
# =============================================================================

WELCOME_MESSAGE = """🎙️ **Bem-vindo ao Narrate!**

Este bot transcreve suas mensagens de voz usando IA local.

**Como usar:**
1. 📤 Envie mensagens de voz
2. ✅ Toque em "Finalizar" quando terminar
3. 📝 Receba a transcrição completa

**Comandos úteis:**
• /start - Iniciar nova sessão
• /status - Ver status atual
• /help - Ajuda detalhada
• /preferences - Configurações de interface

💡 Envie uma mensagem de voz para começar!"""

WELCOME_MESSAGE_SIMPLIFIED = """Bem-vindo ao Narrate!

Este bot transcreve suas mensagens de voz.

Como usar:
1. Envie mensagens de voz
2. Toque em Finalizar quando terminar
3. Receba a transcrição completa

Comandos: /start, /status, /help, /preferences

Envie uma mensagem de voz para começar."""

# =============================================================================
# Session Messages
# =============================================================================

SESSION_CREATED = """✅ <b>Sessão iniciada!</b>

📛 {session_name}
🎙️ {audio_count} áudio(s) recebido(s)

Envie mensagens de voz para gravar.
Toque em <b>Finalizar</b> quando terminar."""

SESSION_CREATED_SIMPLIFIED = "Sessão {session_name} iniciada. {audio_count} áudio(s). Envie mais ou toque Finalizar."

AUDIO_RECEIVED = "🎙️ <b>Áudio {sequence}</b> recebido\n📛 Sessão: {session_name}"

AUDIO_RECEIVED_SIMPLIFIED = "Áudio {sequence} recebido ({session_name})"

SESSION_FINALIZED = "✨ Sessão finalizada!\n\n{audio_count} áudio(s) processado(s)."

SESSION_FINALIZED_SIMPLIFIED = "Sessão finalizada. {audio_count} áudio(s) processado(s)."

SESSION_STATUS = """📊 **Status da Sessão**

🆔 {session_name}
📁 {audio_count} áudio(s)
⏱️ Criada em: {created_at}
📍 Estado: {state}"""

SESSION_STATUS_SIMPLIFIED = """Status da Sessão
Nome: {session_name}
Áudios: {audio_count}
Criada em: {created_at}
Estado: {state}"""

NO_ACTIVE_SESSION = "❌ Nenhuma sessão ativa.\n\nEnvie uma mensagem de voz para iniciar."

NO_ACTIVE_SESSION_SIMPLIFIED = "Nenhuma sessão ativa. Envie uma mensagem de voz para iniciar."

# =============================================================================
# Progress Messages
# =============================================================================

PROGRESS_STARTED = "⏳ Processando {operation_type}..."

PROGRESS_STARTED_SIMPLIFIED = "Processando {operation_type}..."

PROGRESS_UPDATE = "{description}\n{progress_bar} {percentage}%"

PROGRESS_UPDATE_SIMPLIFIED = "{description}: {percentage}% concluído"

PROGRESS_COMPLETE = "✅ Processamento concluído!"

PROGRESS_COMPLETE_SIMPLIFIED = "Processamento concluído."

# =============================================================================
# Error Messages (fallbacks - primary errors in error_catalog.py)
# =============================================================================

GENERIC_ERROR = "❌ Algo inesperado aconteceu. Tente novamente."

GENERIC_ERROR_SIMPLIFIED = "Erro inesperado. Tente novamente."

# =============================================================================
# Confirmation Dialogs
# =============================================================================

SESSION_CONFLICT_TITLE = "⚠️ Sessão em Andamento"

SESSION_CONFLICT_MESSAGE = """Você já tem uma sessão ativa com {audio_count} áudio(s).

O que deseja fazer?"""

SESSION_CONFLICT_SIMPLIFIED = "Sessão ativa com {audio_count} áudio(s). O que deseja fazer?"

CONFIRMATION_MESSAGE = """⚠️ **Confirmação Necessária**

{message}"""

CONFIRMATION_MESSAGE_SIMPLIFIED = "{message}"

# =============================================================================
# Results Messages
# =============================================================================

RESULTS_HEADER = """✅ **Transcrição Concluída**

📁 Sessão: {session_name}
🎙️ {audio_count} áudio(s) processado(s)

**Prévia:**
{preview}"""

RESULTS_HEADER_SIMPLIFIED = """Transcrição Concluída
Sessão: {session_name}
{audio_count} áudio(s)

Prévia:
{preview}"""

# =============================================================================
# Timeout Messages
# =============================================================================

TIMEOUT_WARNING = """⏰ A operação está demorando mais que o esperado.

Tempo decorrido: {elapsed_time}

Deseja continuar aguardando?"""

TIMEOUT_WARNING_SIMPLIFIED = "Operação demorada ({elapsed_time}). Continuar aguardando?"

# =============================================================================
# Help Messages (Contextual)
# =============================================================================

HELP_MESSAGES: dict[str, str] = {
    "SESSION_ACTIVE": """📖 **Sessão Ativa**

/help - Ver esta mensagens avançadas de ajuda.
• Envie mensagens de voz para adicionar à sessão
• Toque em **Finalizar** para processar os áudios
• Toque em **Status** para ver informações da sessão
• Toque em **Cancelar** para descartar a sessão""",
    
    "SESSION_EMPTY": """📖 **Começando**

Para iniciar uma sessão de gravação:
1. Envie uma mensagem de voz
2. Continue enviando quantas quiser
3. Toque em **Finalizar** quando terminar

A sessão será criada automaticamente!""",
    
    "PROCESSING": """📖 **Processamento**

Seus áudios estão sendo transcritos.

• O progresso atualiza a cada 5 segundos
• Você pode **Cancelar** se necessário
• Ao finalizar, você receberá a transcrição""",
    
    "RESULTS": """📖 **Resultados**

• **Ver Completo**: Mostra a transcrição completa
• **Buscar**: Pesquisa em sessões anteriores
• **Pipeline**: Inicia o processamento de artefatos""",
    
    "ERROR_RECOVERY": """📖 **Erro**

Ocorreu um problema. Você pode:
• **Tentar Novamente**: Repete a última ação
• **Cancelar**: Abandona a operação
• **Ajuda**: Ver mais informações""",
    
    "DEFAULT": """📖 **Ajuda**

Envie uma mensagem de voz para começar.
Digite /start para reiniciar.
Digite /status para ver o estado atual.""",
}

HELP_MESSAGES_SIMPLIFIED: dict[str, str] = {
    "SESSION_ACTIVE": "Sessão ativa: envie áudios ou toque Finalizar.",
    "SESSION_EMPTY": "Envie uma mensagem de voz para iniciar.",
    "PROCESSING": "Processando. Aguarde ou cancele.",
    "RESULTS": "Escolha uma ação para os resultados.",
    "ERROR_RECOVERY": "Erro. Tente novamente ou cancele.",
    "DEFAULT": "Envie uma mensagem de voz para começar.",
}

# =============================================================================
# Button Labels
# =============================================================================

BUTTON_FINALIZE = "✅ Finalizar"
BUTTON_FINALIZE_SIMPLIFIED = "Finalizar"

BUTTON_STATUS = "📊 Status"
BUTTON_STATUS_SIMPLIFIED = "Status"

BUTTON_HELP = "❓ Ajuda"
BUTTON_HELP_SIMPLIFIED = "Ajuda"

BUTTON_CANCEL = "❌ Cancelar"
BUTTON_CANCEL_SIMPLIFIED = "Cancelar"

BUTTON_RETRY = "🔄 Tentar Novamente"
BUTTON_RETRY_SIMPLIFIED = "Tentar Novamente"

BUTTON_VIEW_FULL = "📄 Ver Completo"
BUTTON_VIEW_FULL_SIMPLIFIED = "Ver Completo"

BUTTON_SEARCH = "🔍 Buscar"
BUTTON_SEARCH_SIMPLIFIED = "Buscar"

BUTTON_PIPELINE = "🚀 Pipeline"
BUTTON_PIPELINE_SIMPLIFIED = "Pipeline"

BUTTON_PREVIOUS = "⬅️ Anterior"
BUTTON_PREVIOUS_SIMPLIFIED = "Anterior"

BUTTON_NEXT = "➡️ Próximo"
BUTTON_NEXT_SIMPLIFIED = "Próximo"

BUTTON_CLOSE = "✖️ Fechar"
BUTTON_CLOSE_SIMPLIFIED = "Fechar"

BUTTON_CONTINUE_WAIT = "⏳ Continuar Aguardando"
BUTTON_CONTINUE_WAIT_SIMPLIFIED = "Continuar"

BUTTON_FINALIZE_CURRENT = "✅ Finalizar Atual"
BUTTON_FINALIZE_CURRENT_SIMPLIFIED = "Finalizar Atual"

BUTTON_START_NEW = "🆕 Iniciar Nova"
BUTTON_START_NEW_SIMPLIFIED = "Nova Sessão"

BUTTON_RETURN_CURRENT = "↩️ Voltar à Atual"
BUTTON_RETURN_CURRENT_SIMPLIFIED = "Voltar"

BUTTON_RESUME = "▶️ Retomar"
BUTTON_RESUME_SIMPLIFIED = "Retomar"

BUTTON_DISCARD = "🗑️ Descartar"
BUTTON_DISCARD_SIMPLIFIED = "Descartar"

# =============================================================================
# Recovery Prompts
# =============================================================================

RECOVERY_PROMPT = """⚠️ **Sessão Interrompida Detectada**

Uma sessão anterior não foi finalizada corretamente.

📁 {session_name}
🎙️ {audio_count} áudio(s)
📅 Criada em: {created_at}

O que deseja fazer?"""

RECOVERY_PROMPT_SIMPLIFIED = """Sessão interrompida: {session_name}
{audio_count} áudio(s), criada em: {created_at}
O que deseja fazer?"""

# =============================================================================
# Empty/Silent Audio Warning
# =============================================================================

EMPTY_AUDIO_WARNING = """⚠️ **Áudio Vazio Detectado**

O áudio enviado parece estar vazio ou sem fala detectável.

O que deseja fazer?"""

EMPTY_AUDIO_WARNING_SIMPLIFIED = "Áudio vazio ou sem fala. O que deseja fazer?"

# =============================================================================
# Rate Limit Warning
# =============================================================================

RATE_LIMIT_WARNING = """⏳ **Aguarde um momento**

Muitos áudios em sequência. Posição na fila: {queue_position}

Seus áudios serão processados em ordem."""

RATE_LIMIT_WARNING_SIMPLIFIED = "Aguarde. Posição na fila: {queue_position}"

# =============================================================================
# Operation Type Display Names
# =============================================================================

OPERATION_TYPE_NAMES = {
    "TRANSCRIPTION": "transcrição",
    "EMBEDDING": "geração de embeddings",
    "PROCESSING": "processamento",
    "SEARCH": "busca",
}

# =============================================================================
# Helper Functions
# =============================================================================


def get_message(key: str, simplified: bool = False, **kwargs) -> str:
    """Get a message template with optional formatting.
    
    Args:
        key: Message key (module-level constant name)
        simplified: Use simplified version if available
        **kwargs: Format arguments for the message
        
    Returns:
        Formatted message string
    """
    suffix = "_SIMPLIFIED" if simplified else ""
    message_key = f"{key}{suffix}"
    
    # Try to get the message from globals
    message = globals().get(message_key)
    if message is None:
        # Fall back to non-simplified version
        message = globals().get(key, GENERIC_ERROR)
    
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
    return message


def get_button_label(key: str, simplified: bool = False) -> str:
    """Get a button label.
    
    Args:
        key: Button key (e.g., "FINALIZE", "STATUS")
        simplified: Use simplified version (no emojis)
        
    Returns:
        Button label string
    """
    full_key = f"BUTTON_{key}"
    return get_message(full_key, simplified)


def get_help_message(context: str, simplified: bool = False) -> str:
    """Get contextual help message.
    
    Args:
        context: Help context (matches KeyboardType values)
        simplified: Use simplified version
        
    Returns:
        Help message string
    """
    messages = HELP_MESSAGES_SIMPLIFIED if simplified else HELP_MESSAGES
    return messages.get(context, messages.get("DEFAULT", ""))
