"""Adaptive-Card-style rendering for Streamlit.

Each answer is a keyed `st.container` (`card-<status>-…`) that theme.css styles as a
card with a status accent bar; inside: icon header, summary, KPI tiles, Plotly chart,
table (PII cells highlighted), insights and a collapsible SQL block.
"""
import html
import json
import re

import streamlit as st

from agents.schemas import AnswerCard
from ui.charts import build_figure

STATUS_LABEL = {"info": "Insight", "success": "Done", "warning": "Needs attention", "danger": "Blocked"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"\+91[\s-]?[6-9]\d{9}")
_AADHAAR = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")
_SAFE = re.compile(r"\[REDACTED_[A-Z_]+\]|\*{4}\d{0,4}|<\w+_hash:[0-9a-f]+>")


def md_inline(text: str) -> str:
    """Escape, then a tiny safe subset of markdown: **bold**, *italic*, `code`, line breaks."""
    t = html.escape(text or "")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t.replace("\n\n", "<br><br>").replace("\n", "<br>")


def _cell(value: str) -> str:
    v = html.escape(str(value))
    if _SAFE.search(str(value)):
        return f'<span class="pii-safe">🔏 {v}</span>'
    if _EMAIL.search(str(value)) or _PHONE.search(str(value)) or _AADHAAR.search(str(value)):
        return f'<span class="pii-leak">⚠️ {v}</span>'
    return v


def _table_html(columns: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in r) + "</tr>" for r in rows[:15])
    return f'<div class="ac-table-wrap"><table class="ac-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


_FLAG = re.compile(r"^⚠️ \*\*Unverified answer — (.+?)\.\*\* Treat the figures below with caution\.\n\n", re.S)


def render_card(card: AnswerCard, key: str, show_sql: bool = True, meta: str = "") -> None:
    flag = _FLAG.match(card.summary or "")
    summary = card.summary[flag.end():] if flag else card.summary
    with st.container(key=f"card-{card.status}-{key}"):
        if flag:
            st.html(f'''<div class="flag-banner"><div class="flag-icon">🔍</div><div>
              <div class="flag-title">Hallucination check failed — answer not verified</div>
              <div class="flag-detail">{html.escape(flag.group(1))}. Claims below are not supported by the database
              results; treat them with caution.</div></div></div>''')
        st.html(f"""
        <div class="ac-head">
          <div class="ac-icon">{html.escape(card.emoji or '💬')}</div>
          <div><div class="ac-eyebrow {card.status}">{STATUS_LABEL.get(card.status, 'Insight')}</div>
               <div class="ac-title">{html.escape(card.title)}</div></div>
        </div>
        <div class="ac-summary">{md_inline(summary)}</div>""")

        if card.kpis:
            tiles = "".join(
                f'<div class="kpi"><div class="kpi-top"><span>{html.escape(k.icon)}</span>{html.escape(k.label)}</div>'
                f'<div class="kpi-val">{html.escape(k.value)}</div></div>' for k in card.kpis[:4])
            st.html(f'<div class="kpis">{tiles}</div>')

        if card.chart and (fig := build_figure(card.chart)):
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"chart-{key}")

        if card.table and card.table.rows:
            st.html(_table_html(card.table.columns, card.table.rows))

        if card.insights:
            items = "".join(f'<div class="insight">{md_inline(i)}</div>' for i in card.insights[:4])
            st.html(f'<div class="section-label">Key insights</div><div class="insights">{items}</div>')

        if meta:
            st.html(f'<div class="meta">{meta}</div>')
        if show_sql and card.sql_used:
            with st.expander("🧾 SQL used"):
                st.code(card.sql_used, language="sql")


def render_error(message: str, key: str) -> None:
    render_card(AnswerCard(title="Agent error", emoji="💥", status="danger",
                           summary=f"The agent crashed while answering:\n\n`{message[:400]}`"), key, show_sql=False)


def render_thinking(label: str) -> str:
    return (f'<div class="thinking"><div class="dots"><span></span><span></span><span></span></div>'
            f'{html.escape(label)}</div>')


# ---------------------------------------------------------------- guardrail timeline
LAYERS = [
    ("keyword", "⚡", "Keyword"),
    ("jev_input", "🧠", "Jev input"),
    ("pii", "🔏", "PII"),
    ("hitl", "🧑‍⚖️", "Approval"),
    ("grounding", "🔍", "Grounding"),
]
_PRIORITY = ["blocked", "flagged", "pending", "redacted", "error", "info", "pass"]
_STATUS_TEXT = {"pass": "✓ pass", "blocked": "✕ blocked", "redacted": "redacted", "flagged": "⚠ flagged",
                "pending": "⏸ waiting", "info": "armed", "error": "offline", "skipped": "skipped"}


def render_trace(events: list[dict], interrupt: bool = False, decision: dict | None = None,
                 used_write_tool: bool = False) -> None:
    by_layer: dict[str, list[dict]] = {}
    for e in events:
        by_layer.setdefault(e["layer"], []).append(e)
    blocked_at = next((i for i, (l, *_) in enumerate(LAYERS)
                       if any(e["status"] == "blocked" for e in by_layer.get(l, []))), None)

    chips = []
    for i, (layer, icon, name) in enumerate(LAYERS):
        evs = by_layer.get(layer, [])
        if layer == "hitl":
            if interrupt:
                evs = [{"status": "pending", "detail": "human review requested", "ms": None}]
            elif decision:
                evs = [{"status": "pass" if decision["type"] != "reject" else "blocked",
                        "detail": f"human {decision['type']}d" if decision["type"] != "edit" else "human edited", "ms": None}]
            elif not used_write_tool and blocked_at is None:
                evs = [{"status": "pass", "detail": "no write tools used", "ms": None}]
        if layer == "pii" and not evs and blocked_at is None:
            evs = [{"status": "pass", "detail": "no PII found", "ms": None}]
        if layer == "grounding" and interrupt:
            evs = []
        if blocked_at is not None and i > blocked_at:
            status, detail = "skipped", "not reached"
        elif not evs:
            status, detail = "skipped", "—"
        else:
            status = min((e["status"] for e in evs), key=lambda s: _PRIORITY.index(s) if s in _PRIORITY else 99)
            details = [e["detail"] for e in evs if e.get("detail")]
            detail = " · ".join(dict.fromkeys(details))
            ms = sum(e["ms"] or 0 for e in evs if e.get("ms"))
            if ms:
                detail += f" · {ms} ms"
        chips.append(
            f'<div class="chip {status}" title="{html.escape(detail)}"><div class="chip-top">{icon} {name}</div>'
            f'<span class="chip-status">{_STATUS_TEXT.get(status, status)}</span>'
            f'<div class="chip-detail">{html.escape(detail[:110])}</div></div>')
    st.html(f'<div class="trace">{"".join(chips)}</div>')


def render_noguard() -> None:
    items = [("⚡", "Input filter"), ("🔏", "PII"), ("🧑‍⚖️", "Approval"), ("🔍", "Fact check")]
    chips = "".join(f'<div class="chip"><div class="chip-top">{i} {n}</div><span class="chip-status">off</span>'
                    f'<div class="chip-detail">no guardrail</div></div>' for i, n in items)
    st.html(f'<div class="noguard">{chips}</div>')


# ---------------------------------------------------------------- tool activity
def render_tool_log(tools: list[dict], guarded: bool, approved: bool = False) -> None:
    if not tools:
        return
    writes = [t for t in tools if t["write"]]
    label = f"🔧 Tool activity · {len(tools)} call{'s' if len(tools) != 1 else ''}"
    if writes and not guarded:
        label += f" · ⚠️ {len(writes)} write{'s' if len(writes) != 1 else ''} executed without approval"
    with st.expander(label, expanded=bool(writes and not guarded)):
        items = []
        for t in tools:
            args = t["args"].get("query") or ", ".join(f"{k}={v!r}" for k, v in t["args"].items()) or "()"
            out = (t["output"] or "")[:400]
            cls = "tool-item write" + (" approved" if guarded and approved else "") if t["write"] else "tool-item"
            tag = ""
            if t["write"]:
                tag = ('<span class="tool-tag ok">human-approved</span>' if guarded and approved
                       else '<span class="tool-tag">no approval</span>' if not guarded else "")
            items.append(f'<div class="{cls}"><div class="tool-name">{html.escape(t["name"])} {tag}</div>'
                         f'<div class="tool-code">{html.escape(str(args))}</div>'
                         f'<div class="tool-out">→ {html.escape(out)}</div></div>')
        st.html(f'<div class="tool-log">{"".join(items)}</div>')


# ---------------------------------------------------------------- HITL
def sql_preview(name: str, args: dict) -> str:
    if name == "delete_student_records":
        return f"DELETE FROM students\nWHERE {args.get('where_clause', '?')};"
    if name == "update_student_records":
        return f"UPDATE students\nSET {args.get('set_clause', '?')}\nWHERE {args.get('where_clause', '?')};"
    return json.dumps(args, indent=2)


def highlight_sql(sql: str) -> str:
    out = html.escape(sql)
    for kw in ("DELETE FROM", "UPDATE", "SET", "WHERE"):
        out = re.sub(rf"\b{kw}\b", f'<span class="kw">{kw}</span>', out)
    return out
