"""🛡️ Guardrails Arena — Nagarro Flo demo.

Same question → two agents (same model, prompt, tools). Left: no guardrails.
Right: Keyword → Jev → PII → Human-in-the-loop → Grounding.

Run:  uv run streamlit run app.py
"""
import html
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import streamlit as st

import config  # noqa: F401  (loads .env, LangSmith settings)
from agents.guarded import build_guarded_agent
from agents.runner import TurnResult, resume_turn, run_turn
from agents.tools import count_matching
from agents.unguarded import build_unguarded_agent
from data.seed_db import DB_PATHS, ensure_dbs, reset_dbs, row_count
from ui.cards import (highlight_sql, md_inline, render_card, render_error, render_noguard, render_thinking,
                      render_tool_log, render_trace, sql_preview)
from ui.scenarios import SCENARIOS

st.set_page_config(page_title="Guardrails Arena · Nagarro Flo", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")
st.html(f"<style>{(Path(__file__).parent / 'ui' / 'theme.css').read_text()}</style>")

MODELS = {"Gemini 3.8 Flash · best answers": "gemini-3.8-flash", "Gemini 3.5 Flash-Lite · fastest": "gemini-3.5-flash-lite"}
TOTAL_ROWS = 800

ensure_dbs()
ss = st.session_state
ss.setdefault("turns", [])
ss.setdefault("pending_q", None)


@st.cache_resource(show_spinner=False)
def get_agents(model: str):
    return build_unguarded_agent(model), build_guarded_agent(model)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.html('<div class="side-title">🎬 Demo scenarios</div>'
            '<div class="side-sub">One click sends the same question to both agents.</div>')
    for group, items in SCENARIOS:
        st.html(f'<div class="side-group">{group}</div>')
        for label, prompt in items:
            if st.button(label, key=f"sc-{label}", help=prompt):
                ss.pending_q = prompt

    st.html('<div class="side-group">Controls</div>')
    if st.button("🔄 Reset databases", help="Restore both databases to the original 800 students"):
        reset_dbs()
        st.toast("Both databases restored to 800 students", icon="🔄")
    if st.button("🧹 Clear chat", help="Remove all answers from the screen"):
        ss.turns = []
        st.rerun()
    with st.expander("⚙️ Settings"):
        model_label = st.selectbox("Model (both agents)", list(MODELS))
        show_sql = st.toggle("Show SQL", value=True)
        show_tools = st.toggle("Show tool activity", value=True)

unguarded_agent, guarded_agent = get_agents(MODELS[model_label])

# ------------------------------------------------------------------ title
st.html('<div class="app-title"><div class="app-title-icon">🛡️</div><div class="app-title-text">Guardrails Arena</div></div>')


def db_badge(side: str) -> str:
    n = row_count(DB_PATHS[side])
    if n is None:
        return '<div class="db-badge danger">🗄️ <b>table dropped</b></div>'
    cls = "db-badge danger" if n < TOTAL_ROWS else "db-badge"
    delta = f" <span>(−{TOTAL_ROWS - n})</span>" if n < TOTAL_ROWS else ""
    return f'<div class="{cls}">🗄️ <b>{n}</b> students{delta}</div>'


left, right = st.columns(2, gap="large")
left.html(f"""<div class="panel-head unguarded"><div><div class="panel-title">🔓 Unguarded agent</div>
<div class="panel-desc">Raw LLM + tools. Executes whatever it decides.</div></div>{db_badge('unguarded')}</div>""")
right.html(f"""<div class="panel-head guarded"><div><div class="panel-title">🛡️ Guarded agent</div>
<div class="panel-desc">5-layer guardrail stack around the same agent.</div></div>{db_badge('guarded')}</div>""")


# ------------------------------------------------------------------ rendering
def meta_line(r: TurnResult) -> str:
    parts = [f"⏱️ {r.ms / 1000:.1f}s"]
    parts.append(f"🤖 {r.llm_calls} LLM call{'s' if r.llm_calls != 1 else ''}" if r.llm_calls else "🤖 0 LLM calls · 0 tokens")
    return "".join(f"<span>{p}</span>" for p in parts)


def render_unguarded(r: TurnResult, key: str) -> None:
    render_noguard()
    if r.error:
        render_error(r.error, key)
        return
    if show_tools:
        render_tool_log(r.tools, guarded=False)
    render_card(r.card, key, show_sql, meta_line(r))


def render_hitl(turn: dict, idx: int) -> None:
    r: TurnResult = turn["g"]
    action = r.interrupt["action_requests"][0]
    allowed = r.interrupt["review_configs"][0]["allowed_decisions"]
    name, args = action["name"], action["args"]
    affected = count_matching(DB_PATHS["guarded"], args.get("where_clause", "1=0"))
    verb = "permanently deleted" if name == "delete_student_records" else "modified"
    with st.container(key=f"card-pending-hitl-{idx}"):
        st.html(f"""
        <div class="hitl-banner"><div class="hitl-icon">🧑‍⚖️</div>
          <div><div class="ac-eyebrow warning">Human approval required</div>
               <div class="ac-title">The agent wants to run <code>{html.escape(name)}</code></div></div></div>
        <div class="ac-summary">Execution is <b>paused</b> — nothing has changed yet. Review the exact action below.</div>
        <div class="hitl-sql">{highlight_sql(sql_preview(name, args))}</div>
        <div class="impact">⚠️ <span><b>{affected}</b> of {row_count(DB_PATHS['guarded']) or 0} student records will be {verb}.</span></div>
        """)
        edited = None
        if "edit" in allowed:
            with st.expander("✏️ Edit before approving"):
                set_c = st.text_input("SET", args.get("set_clause", ""), key=f"edit-set-{idx}")
                where_c = st.text_input("WHERE", args.get("where_clause", ""), key=f"edit-where-{idx}")
                if set_c != args.get("set_clause") or where_c != args.get("where_clause"):
                    edited = {"set_clause": set_c, "where_clause": where_c}
        reason = st.text_input("Reason (sent back to the agent on reject)", "Too risky — needs Dean's approval",
                               key=f"reason-{idx}")
        b1, b2, _ = st.columns([1, 1, 2])
        decision = None
        if b1.button("✅ Approve" if not edited else "✅ Approve edited", key=f"approve-{idx}", use_container_width=True):
            decision = ({"type": "edit", "edited_action": {"name": name, "args": edited}} if edited
                        else {"type": "approve"})
        if b2.button("❌ Reject", key=f"reject-{idx}", use_container_width=True):
            decision = {"type": "reject", "message": reason}
    if decision:
        with st.spinner("Resuming agent…"):
            turn["g"] = resume_turn(guarded_agent, r.thread_id, decision, r.events)
            turn["g_tools_before"] = r.tools
        st.rerun()


def render_guarded(turn: dict, idx: int) -> None:
    r: TurnResult = turn["g"]
    used_write = any(t["write"] for t in r.tools)
    render_trace(r.events, interrupt=bool(r.interrupt), decision=r.decision, used_write_tool=used_write)
    if r.error:
        render_error(r.error, f"g{idx}")
        return
    if r.interrupt:
        render_hitl(turn, idx)
        return
    if r.decision:
        d = r.decision
        label = {"approve": "✅ Approved by human", "edit": "✏️ Edited & approved by human",
                 "reject": f"❌ Rejected by human — “{html.escape(d.get('message', ''))}”"}[d["type"]]
        st.html(f'<div class="decision {d["type"]}">{label}</div>')
    if show_tools:
        render_tool_log(r.tools, guarded=True, approved=bool(r.decision and r.decision["type"] != "reject"))
    render_card(r.card, f"g{idx}", show_sql, meta_line(r))


def question_bubble(q: str, n: int) -> None:
    st.html(f'<div class="q-row"><div class="q-bubble"><span class="q-num">Q{n}</span>{md_inline(q)}</div></div>')


# ------------------------------------------------------------------ new question
question = st.chat_input("Ask both agents about student placements…")
question = question or ss.pending_q
ss.pending_q = None

if question:
    question_bubble(question, len(ss.turns) + 1)
    lcol, rcol = st.columns(2, gap="large")
    holders = {"u": lcol.empty(), "g": rcol.empty()}
    holders["u"].html(render_thinking("Unguarded agent is working…"))
    holders["g"].html(render_thinking("Guarded agent is checking & working…"))
    turn = {"q": question, "u": None, "g": None}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(run_turn, unguarded_agent, question): "u",
                   pool.submit(run_turn, guarded_agent, question): "g"}
        for fut in as_completed(futures):
            side = futures[fut]
            turn[side] = fut.result()
            r = turn[side]
            done = "✅" if not r.error else "💥"
            holders[side].html(render_thinking(f"{done} Finished in {r.ms / 1000:.1f}s — rendering…"))
    ss.turns.append(turn)
    st.rerun()

# ------------------------------------------------------------------ history (newest first)
if not ss.turns:
    st.html("""<div class="empty"><div class="empty-icon">👋</div>
      <div class="empty-title">Ask one question, compare two agents</div>
      <div class="empty-sub">Start with a quick scenario below, pick one from the sidebar, or type your own question.</div></div>""")
    quick = [("📊 Placement by department", SCENARIOS[0][1][0][1]), ("📇 Contact details leak", SCENARIOS[1][1][0][1]),
             ("🗑️ Delete records", SCENARIOS[3][1][0][1]), ("📉 Benchmark vs IIT Bombay", SCENARIOS[4][1][0][1])]
    _, *cols, _ = st.columns([0.5, 1, 1, 1, 1, 0.5])
    for col, (label, prompt) in zip(cols, quick):
        if col.button(label, key=f"quick-{label}", help=prompt, use_container_width=True):
            ss.pending_q = prompt
            st.rerun()

for idx in range(len(ss.turns) - 1, -1, -1):
    turn = ss.turns[idx]
    question_bubble(turn["q"], idx + 1)
    lcol, rcol = st.columns(2, gap="large")
    with lcol:
        render_unguarded(turn["u"], f"u{idx}")
    with rcol:
        render_guarded(turn, idx)
