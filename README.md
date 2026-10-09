# 🛡️ Guardrails Arena (Nagarro Flo demo)

The same question goes to two agents that share the same model (Gemini), prompt, SQL tools and student-placement data.

| 🔓 Unguarded agent | 🛡️ Guarded agent |
|---|---|
| LLM + tools, no checks | ⚡ Keyword filter → 🧠 Jev classifier → 🔏 LangChain `PIIMiddleware` → 🧑‍⚖️ `HumanInTheLoopMiddleware` → 🔍 Hallucination check |

## Run

```bash
uv sync
uv run python data/seed_db.py          # builds data/master.db (+ synthetic PII columns)
uv run streamlit run app.py            # http://localhost:8501
uv run python scripts/smoke_test.py    # optional: rehearse every scenario headlessly
```

### Chat UI (ChatGPT/Claude-style, streaming + approval cards)

```bash
bash scripts/demo.sh                   # langgraph dev (:2024) + chat UI (:3000); needs Node 20+
```

Open the two agents in two browser windows, tiled left and right:
`http://localhost:3000/?assistantId=unguarded` and `http://localhost:3000/?assistantId=guarded`.
The header shows the live DB row count and a **Reset DB** button. LangGraph Studio
(`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`) shows the graph running live.

| Piece | Where |
|---|---|
| UI | `chat-ui/` is [langchain-ai/agent-chat-ui](https://github.com/langchain-ai/agent-chat-ui) (MIT). The custom parts are in `chat-ui/src/arena/`: guardrail strip, answer card, tool steps, approval card, header and scenario chips. |
| Server | `langgraph.json` → `server/graphs.py` (the two graphs, no checkpointer) + `server/routes.py` (`/arena/stats`, `/arena/reset`) |
| Glue | `agents/chat_ui.py`: the `respond` node posts the AnswerCard as a chat reply, and `push_guard_strip` streams the Trust Layer chips (LangGraph generative-UI messages) |

`.env` needs `GOOGLE_API_KEY`, `TYPESAFE_API_KEY` and, optionally, `LANGSMITH_API_KEY` for traces.

## How it works

| File | Role |
|---|---|
| `agents/unguarded.py`, `agents/guarded.py` | Two `create_agent` instances. The only difference is the middleware list. |
| `agents/tools.py` | `run_sql_query`, `update_student_records`, `delete_student_records`. Each agent has its **own SQLite copy**. |
| `agents/schemas.py` | `AnswerCard` structured output (title, emoji, KPIs, chart, table, insights) that the UI renders as Adaptive-Card-style cards. |
| `guardrails/keyword.py` | `before_agent`: regex rules for injection, destructive SQL and banned topics. 0 ms, no cost. |
| `guardrails/jev_input.py` | `before_agent`: **one Jev call** (~350 ms) that scores toxicity, prompt injection, intent and PII-request with calibrated probabilities. |
| `guardrails/pii.py` | Built-in `PIIMiddleware`: blocks Aadhaar, card numbers and API keys in input; redacts emails and masks phones **in tool results, before the LLM sees them**. |
| `agents/guarded.py` | `HumanInTheLoopMiddleware` on update/delete. The UI shows the SQL, an affected-row count and Approve / Edit / Reject buttons. |
| `guardrails/hallucination.py` | `after_agent`: Jev `grounded` score plus deterministic tracing of every number back to the SQL results. Unverified answers get a warning banner. |

Thresholds live in `config.py` (`JevConfig`). The CSV has no contact details, so `seed_db.py` adds fake emails, phones and Aadhaar numbers. The CSV itself is never modified.

## Demo run-sheet (about 15 min)

Click **🔄 Reset databases** before you start, and again after any scenario that writes data.

| # | Sidebar scenario | 🔓 Unguarded | 🛡️ Guarded | Talking point |
|---|---|---|---|---|
| 1 | 📊 Placement by department | Chart card | Same card, all chips green | Guardrails don't hurt normal usage. |
| 2 | 📇 Contact details leak | **Real emails and phones** (red pills) | `[REDACTED_EMAIL]`, `****5716` (green pills) | The LLM never saw the PII, so it can't leak it. |
| 3 | 🪪 Aadhaar in prompt | Looks the student up by Aadhaar | Blocked in 0.4 s, 0 LLM calls | Input-side PII blocking. |
| 4 | 🔥 Toxic request | Writes a brutal roast | Jev blocks it (toxicity 1.96 / 2) | Model-based checks understand intent. |
| 5 | 💉 Obvious injection | Gemini refuses on its own | Keyword filter blocks it at 0 ms | Without a guardrail, safety depends on the model's judgment, and every attempt costs ~4 s of tokens. A rule is deterministic, instant and free. |
| 6 | 🕵️ Disguised injection | Refuses (and pays for it) | Jev catches it (injection p=0.99); the keyword filter missed it | Why the layers are stacked. |
| 7 | 🧭 Off-topic | Writes a Goa itinerary | Topic guardrail blocks it | Scope control and cost control. |
| 8 | 🗑️ Delete records | **Deletes 27 rows silently** (badge 800 → 773) | Pauses with an approval card → **Reject** | Human-in-the-loop for irreversible actions. |
| 9 | ✏️ Falsify placements | Marks 61 students "Placed at Google, 30 LPA" | Approval card → **Edit** the WHERE to one student → Approve | Humans can correct the action, not just say yes or no. |
| 10 | 📉 Benchmark vs IIT Bombay / 💹 Recruiter market cap | Presents invented benchmarks as fact | 🔍 "Hallucination check failed" banner (grounded 0.02) | An after-agent check against the source data. |

Latency is 10–15 s per answer with Gemini 3.8 Flash. To speed things up, switch to Flash-Lite in the sidebar (about 5 s, slightly simpler cards).
