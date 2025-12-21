"""Prompt injector for oracle context injection.

Per contracts/context-builder.md for 007-contextual-oracle-feedback.

This module handles injecting context into oracle prompts,
supporting both placeholder replacement and append modes.
"""

import logging

from src.models.oracle import Oracle

logger = logging.getLogger(__name__)


class PromptInjector:
    """
    Injects context into oracle prompts.
    
    Per FR-005: Inject context into oracle placeholder (default {{CONTEXT}}).
    Fallback: append context at end if placeholder missing.
    """
    
    def inject(self, oracle: Oracle, context: str) -> str:
        """
        Inject context into oracle prompt.
        
        If the oracle prompt contains the placeholder, replace it with context.
        Otherwise, append context at the end of the prompt.
        
        Args:
            oracle: Oracle with prompt_content and placeholder
            context: Context string to inject
            
        Returns:
            Complete prompt with context injected
        """
        if oracle.has_placeholder():
            # Replace placeholder with context
            result = oracle.prompt_content.replace(oracle.placeholder, context)
            logger.debug(
                f"Injected context into oracle '{oracle.name}' "
                f"(replaced placeholder '{oracle.placeholder}')"
            )
            return result
        else:
            # Append context at the end
            result = f"{oracle.prompt_content}\n\n## Contexto do Usuário\n\n{context}"
            logger.debug(
                f"Injected context into oracle '{oracle.name}' "
                f"(appended, no placeholder found)"
            )
            return result
    
    def preview_injection_point(self, oracle: Oracle) -> str:
        """
        Get a preview of where context will be injected.
        
        Useful for debugging and documentation.
        
        Args:
            oracle: Oracle to preview
            
        Returns:
            Description of injection method
        """
        if oracle.has_placeholder():
            return f"Placeholder replacement at '{oracle.placeholder}'"
        else:
            return "Appended at end of prompt (no placeholder found)"
