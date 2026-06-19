"""JobHunter core.ai_providers package."""
from core.ai_providers.base_provider import BaseAIProvider
from core.ai_providers.ollama_provider import OllamaProvider

__all__ = ["BaseAIProvider", "OllamaProvider"]
