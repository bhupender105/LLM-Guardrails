from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from config import llm_config


@lru_cache(maxsize=4)
def get_llm(model: str | None = None) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=model or llm_config.AGENT_MODEL, temperature=0, thinking_level=llm_config.THINKING_LEVEL)
