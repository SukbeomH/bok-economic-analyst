"""Create and cache the configured chat and embedding clients."""

from langchain_anthropic import ChatAnthropic
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from core.config import Config
from core.logger import logger


class ModelFactory:
    """Use separate credentials and endpoints for chat and document embeddings."""

    def __init__(self):
        missing = Config.validate_required_settings()
        if missing:
            raise ValueError("모델 설정 오류: " + "; ".join(missing.values()))
        self._chat_model_cache = {}
        self._embedding_model_cache = None

    def get_chat_model(self, temperature: float = 0) -> BaseChatModel:
        """Return a chat client cached by temperature."""
        if temperature not in self._chat_model_cache:
            options = {
                "model": Config.LLM_MODEL,
                "api_key": Config.LLM_API_KEY,
                "base_url": Config.chat_base_url(),
                "temperature": temperature,
                "max_retries": 5,
                "timeout": 60,
            }
            if Config.LLM_PROVIDER == "claude":
                model = ChatAnthropic(**options, max_tokens=4096)
            else:
                model = ChatOpenAI(**options)
            self._chat_model_cache[temperature] = model
            logger.info("[model] 채팅 모델 생성: provider=%s", Config.LLM_PROVIDER)
        return self._chat_model_cache[temperature]

    def get_embedding_model(self) -> Embeddings:
        """Return the independently configured embedding client."""
        if self._embedding_model_cache is None:
            self._embedding_model_cache = OpenAIEmbeddings(
                model=Config.EMBEDDING_MODEL,
                api_key=Config.EMBEDDING_API_KEY,
                base_url=Config.embedding_base_url(),
                check_embedding_ctx_length=Config.EMBEDDING_PROVIDER == "openai",
                model_kwargs={"encoding_format": "float"},
                max_retries=5,
                request_timeout=60,
            )
            logger.info("[model] 임베딩 모델 생성: provider=%s", Config.EMBEDDING_PROVIDER)
        return self._embedding_model_cache

    def clear_cache(self):
        """Discard both client caches."""
        self._chat_model_cache.clear()
        self._embedding_model_cache = None
