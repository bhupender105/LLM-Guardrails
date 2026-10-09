"""Trust Layer — the guarded graph's fixed entry and exit nodes (same shape as the sales-agent).

    START → [trustlayer_input] → agent ⇄ tools → [trustlayer_tools] → … → finalize → [trustlayer_output] → END
                  └─ blocked ──────────────────────────────────────────────────────────┘

  * trustlayer_input   — BEFORE the agent: ⚡ keyword → 🧠 Jev (toxicity / injection / intent) → 🔏 PII.
                         Any block skips the LLM entirely.
  * trustlayer_tools   — DURING the agent loop: 🔏 PII scrub of SQL results before the LLM reads them.
  * trustlayer_output  — AFTER the agent: 🔍 grounding (Jev) + number tracing on the final AnswerCard.

Every step appends an event to `guard_events` stamped with `phase` ("input" | "tools" | "output");
`trustlayer.trace.format_turn()` renders them as a readable before / agent / after trace.
The individual checks live in `guardrails/`; new guardrails are wired in from these nodes.
"""
from trustlayer.input_node import trustlayer_input_node
from trustlayer.output_node import trustlayer_output_node
from trustlayer.tools_node import trustlayer_tools_node

__all__ = ["trustlayer_input_node", "trustlayer_tools_node", "trustlayer_output_node"]
