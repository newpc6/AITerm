from app.models.model_setting import ModelConfig
from app.services.llm_providers.openai import OpenAIProvider


def create_llm_client(model_config: ModelConfig, debug_logging: bool = False):
    api_type = getattr(model_config, 'api_type', 'openai') or 'openai'

    if api_type in ("openai", "ollama", "deepseek"):
        client = OpenAIProvider(model_config)
    elif api_type == "anthropic":
        raise NotImplementedError("Anthropic provider is not yet implemented")
    else:
        raise ValueError(f"Unsupported API type: {api_type}")

    client.debug_logging = debug_logging
    return client
