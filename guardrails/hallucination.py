"""Layer 5 — after-agent hallucination / output check.

Two independent signals:
1. Deterministic: every number in the answer card must trace back to a SQL result
   (with rounding tolerance and simple derived ratios).
2. Jev: `grounded` (Noul) — is the answer supported by the tool results? plus
   `answer_toxicity` (Score) on the final text.
If either fails, the card is downgraded to a warning with a visible banner instead of
being presented as fact.
"""
import json
import re
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from langchain_typesafe import Noul, Score

from agents.schemas import AnswerCard
from config import jev_config
from guardrails.jev import jev_classify
from guardrails.state import GuardState, event, last_user_text

_NUM = re.compile(r"(?<![A-Za-z\d.])(-?\d[\d,]*(?:\.\d+)?)(\s*%)?")


def _claims(text: str) -> list[tuple[float, int, bool]]:
    """(value, decimals, is_percent) for every number in the text."""
    out = []
    for raw, pct in _NUM.findall(text):
        clean = raw.replace(",", "")
        try:
            out.append((float(clean), len(clean.split(".")[1]) if "." in clean else 0, bool(pct)))
        except ValueError:
            pass
    return out


def _numbers(text: str) -> list[float]:
    return [v for v, _, _ in _claims(text)]


def _card_claims(card: AnswerCard) -> list[tuple[float, int, bool]]:
    text = " ".join([card.summary, *(k.value for k in card.kpis), *card.insights])
    claims = _claims(text)
    if card.chart:
        for s in card.chart.series:
            for v in s.values:
                d = min(len(repr(v).split(".")[1]) if "." in repr(v) else 0, 2)
                claims.append((v, d, False))
    # Ignore tiny integers and years — rarely claims ("top 5", "2024 batch")
    return [c for c in claims
            if not (abs(c[0]) <= 10 and c[1] == 0) and not (2000 <= c[0] <= 2100 and c[1] == 0)]


def _matches(value: float, decimals: int, facts: list[float]) -> bool:
    return any(round(f, decimals) == round(value, decimals) for f in facts)


def _ratios(facts: list[float]) -> list[float]:
    """Percentages the model may legitimately compute (a / b * 100)."""
    small = facts[:80]
    return [a / b * 100 for a in small for b in small if b and 0 < a <= b]


class HallucinationGuard(AgentMiddleware):
    state_schema = GuardState
    name = "HallucinationGuard"

    def after_agent(self, state: GuardState, runtime: Runtime) -> dict[str, Any] | None:
        card: AnswerCard | None = state.get("structured_response")
        events = state.get("guard_events", [])
        if card is None or any(e["status"] == "blocked" and e["layer"] != "hitl" for e in events):
            return None
        started = time.perf_counter()

        # Tool results of the current turn (after the last human message)
        msgs = state["messages"]
        start = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
        tool_outputs = [m.content for m in msgs[start:] if isinstance(m, ToolMessage) and isinstance(m.content, str)]

        # 1) deterministic number tracing
        facts = [n for t in tool_outputs for n in _numbers(t)]
        ratios = _ratios(facts)
        claimed = _card_claims(card)
        verified = sum(_matches(v, d, facts) or (pct and _matches(v, d, ratios)) for v, d, pct in claimed)
        ratio = verified / len(claimed) if claimed else 1.0

        # 2) Jev grounding + output toxicity
        answer_text = card.model_dump_json(exclude={"sql_used"})
        scores: dict[str, Any] = {"numbers_verified": f"{verified}/{len(claimed)}"}
        try:
            res = jev_classify(
                state={
                    "user_question": last_user_text(state),
                    "database_results": tool_outputs[-6:] or ["<no database query was run>"],
                    "assistant_answer": json.loads(answer_text),
                },
                questions={
                    "grounded": Noul(
                        instructions="Every number, name and factual claim in assistant_answer is directly supported "
                        "by database_results (or is a correct calculation from them). Claims about entities or "
                        "data that do not appear in database_results are NOT supported.",
                    ),
                    "answer_toxicity": Score(
                        instructions="How toxic, insulting or demeaning is the assistant_answer?",
                        criteria=["Not toxic", "Mildly rude", "Insulting or demeaning"],
                    ),
                },
                run_name="jev_output_grounding",
            )
            scores["grounded"] = round(res.answers["grounded"].noul, 2)
            scores["answer_toxicity"] = round(res.answers["answer_toxicity"].score, 2)
        except Exception as e:
            scores["jev_error"] = str(e)[:120]

        problems = []
        if scores.get("grounded", 1.0) < jev_config.GROUNDED_MIN:
            problems.append(f"low grounding ({scores['grounded']:.2f})")
        if claimed and len(claimed) >= 2 and ratio < 0.5:
            problems.append(f"only {verified}/{len(claimed)} numbers trace to SQL results")
        if not tool_outputs and claimed:
            problems.append("numbers stated without querying the database")
        if scores.get("answer_toxicity", 0.0) >= jev_config.TOXICITY_BLOCK:
            problems.append(f"toxic output ({scores['answer_toxicity']:.2f})")

        detail = f"grounded {scores.get('grounded', '–')} · numbers {verified}/{len(claimed)}"
        if not problems:
            return {"guard_events": [event("grounding", "pass", "Hallucination check", detail, scores, started)]}

        flagged = card.model_copy(update={
            "status": "warning",
            "summary": f"⚠️ **Unverified answer — {'; '.join(problems)}.** Treat the figures below with caution.\n\n"
                       + card.summary,
        })
        if scores.get("answer_toxicity", 0.0) >= jev_config.TOXICITY_BLOCK:
            flagged = AnswerCard(title="Response withheld", emoji="🛡️", status="danger",
                                 summary="The generated answer failed the output safety check and was withheld.")
        return {
            "structured_response": flagged,
            "guard_events": [event("grounding", "flagged", "Hallucination check",
                                   f"{detail} → {'; '.join(problems)}", scores, started)],
        }
