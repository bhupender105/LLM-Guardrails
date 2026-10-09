"""Jev (TypeSafe "System One") through LangChain — so every call shows up as a run in LangSmith.

Jev is a classifier, not a text model: hand it a state and typed questions (Noul / Choice / Score) and it
returns calibrated probabilities in ~350 ms. `langchain_typesafe.TypeSafeClassifier` is a LangChain Runnable,
so each call is traced as an "llm" run (state, questions, answers, token usage) nested under the
trustlayer node that made it, labelled by `run_name` and tagged "jev".

ONE module-level client on purpose: it wraps pooled httpx clients, so reusing it keeps the TLS session warm
(cold ≈ 626 ms vs ≈ 350 ms warm). Auth is TYPESAFE_API_KEY, read by the SDK itself.
"""
import warnings

from langchain_core._api import LangChainBetaWarning
from langchain_typesafe import ClassifierResponse, Question, State, TypeSafeClassifier

from config import jev_config

with warnings.catch_warnings():
    warnings.simplefilter("ignore", LangChainBetaWarning)  # TypeSafeClassifier is @beta
    jev_client = TypeSafeClassifier(model=jev_config.JEV_MODEL, timeout=jev_config.JEV_TIMEOUT_S)


def jev_classify(state: State, questions: dict[str, Question], run_name: str = "jev") -> ClassifierResponse:
    """One traced Jev call. Raises on timeout / API error — callers decide how to fail (we fail open)."""
    return jev_client.invoke(
        {"state": state, "questions": questions},
        config={"run_name": run_name, "tags": ["jev"]},
    )
