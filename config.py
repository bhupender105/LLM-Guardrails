import os
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parent


class BaseSettingsWrapper(BaseSettings):
    class Config:
        env_file = str(ROOT_DIR / ".env")
        case_sensitive = True
        extra = "allow"


class LangSmithConfig(BaseSettingsWrapper):
    LANGSMITH_TRACING: str = "true"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "Flo-Guardrails-Demo"


class LLMConfig(BaseSettingsWrapper):
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_BIG_MODEL: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"
    # Model both agents use — same model on both sides keeps the comparison fair.
    AGENT_MODEL: str = "gemini-3.8-flash"
    THINKING_LEVEL: str = "low"


class JevConfig(BaseSettingsWrapper):
    """Jev / TypeSafe "System One" — a classifier, not a text model: one call returns
    calibrated probabilities over typed questions in ~350 ms. Used as the input
    guardrail (toxicity / prompt injection / intent) and the after-agent grounding
    check. Auth is TYPESAFE_API_KEY, read by the SDK itself.
    """
    TYPESAFE_API_KEY: str = ""
    JEV_MODEL: str = "jev-latest"
    JEV_TIMEOUT_S: float = 5.0           # HTTP timeout of the shared classifier client (fail-open on expiry)
    # Thresholds — a request is blocked when any of these is crossed.
    TOXICITY_BLOCK: float = 1.0          # expected score on the 0..2 rubric
    INJECTION_BLOCK: float = 0.7         # noul probability
    HARMFUL_INTENT_BLOCK: float = 0.8    # choice probability of "harmful"
    OFF_TOPIC_BLOCK: float = 0.7         # choice probability of "off_topic"
    GROUNDED_MIN: float = 0.3            # below this the answer is flagged


class DataConfig(BaseSettingsWrapper):
    CSV_PATH: str = str(ROOT_DIR / "student_placements.csv")
    DATA_DIR: str = str(ROOT_DIR / "data")


langsmith_config = LangSmithConfig()
llm_config = LLMConfig()
jev_config = JevConfig()
data_config = DataConfig()

# Propagate keys into os.environ so the SDKs (LangSmith, Gemini, TypeSafe) pick them up
for key, value in {
    "LANGSMITH_TRACING": langsmith_config.LANGSMITH_TRACING if langsmith_config.LANGSMITH_API_KEY else "false",
    "LANGSMITH_ENDPOINT": langsmith_config.LANGSMITH_ENDPOINT,
    "LANGSMITH_API_KEY": langsmith_config.LANGSMITH_API_KEY,
    "LANGSMITH_PROJECT": langsmith_config.LANGSMITH_PROJECT,
    "GOOGLE_API_KEY": llm_config.GOOGLE_API_KEY,
    "TYPESAFE_API_KEY": jev_config.TYPESAFE_API_KEY,
}.items():
    if value:
        os.environ.setdefault(key, value)
